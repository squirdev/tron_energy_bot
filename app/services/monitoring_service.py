import logging
from datetime import datetime
from typing import List, Optional
import httpx
from telegram.ext import Application
from telegram.constants import ParseMode

from app.db.models import MonitorAddress
from app.services.tron_service import TronService, TransactionData

class MonitoringService:
    """
    封装所有与地址监听相关的业务逻辑，适配轮询架构。
    """
    # 这个类变量将在 main.py 启动时被注入，用于发送 Telegram 消息
    ptb_app: Optional[Application] = None

    
    @staticmethod
    async def handle_webhook_transaction(tx: TransactionData):
        """
        处理单笔交易 (无论是来自支付 worker 还是地址监听 worker)，
        找到所有监听该地址的用户并发送通知。
        """
        # 一笔交易涉及双方地址，我们必须两个都检查
        addresses_involved = {tx.from_address, tx.to_address}
        
        for address in addresses_involved:
            # 找到所有正在监听这个特定地址的用户条目
            monitor_entries = await MonitoringService.get_users_monitoring_address(address)
            if not monitor_entries:
                continue

            logging.info(f"为地址 {address} 找到 {len(monitor_entries)} 个监听用户 | 交易ID: {tx.tx_id}")

            # 即使有多个用户监听同一个地址，我们也只为这个地址查询一次余额，提高效率
            latest_balances = await TronService.get_account_details(address)
            
            for entry in monitor_entries:
                # 判断这笔交易对于被监听的地址是收入还是支出
                is_income = tx.to_address == entry.address
                is_outcome = tx.from_address == entry.address
                
                # 如果一个地址给自己转账，它既是收入也是支出，我们都应该继续处理
                if not is_income and not is_outcome:
                    continue
                
                # --- 根据用户设置的开关进行判断 ---
                tx_type_str = ""
                should_notify = False
                if is_income and entry.notify_on_incoming:
                    should_notify = True
                    tx_type_str = "收入"
                # 使用 elif 避免给自己转账时 tx_type_str 被覆盖为 "支出"
                elif is_outcome and entry.notify_on_outgoing:
                    should_notify = True
                    tx_type_str = "支出"

                if should_notify:
                    if tx.token_symbol == 'USDT' and not entry.notify_usdt:
                        should_notify = False
                    elif tx.token_symbol == 'TRX' and not entry.notify_trx:
                        should_notify = False
                
                if should_notify and MonitoringService.ptb_app and latest_balances:
                    nickname = f" ({entry.nickname})" if entry.nickname != '未设置备注' else ""
                    time_str = datetime.fromtimestamp(tx.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 动态构建符合您截图的完美消息
                    header = f"🔴🔴 {tx_type_str}: {'+' if is_income else '-'}{tx.amount} {tx.token_symbol} 【#🔔监听列表】"
                    
                    body = (
                        f"`{entry.address}`\n"
                        f"TRX余额: {latest_balances.trx_balance}\n"
                        f"USDT余额: {latest_balances.usdt_balance}\n\n"
                        f"交易币种: #{tx.token_symbol}\n"
                        f"交易类型: #{tx_type_str}\n"
                        f"交易对象: `{tx.from_address if is_income else tx.to_address}`\n"
                        f"⏰交易时间: {time_str}"
                    )
                    
                    message = f"{header}\n\n{body}"

                    try:
                        await MonitoringService.ptb_app.bot.send_message(
                            chat_id=entry.user_id, text=message, parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logging.error(f"向用户 {entry.user_id} 发送格式化通知失败: {e}")

    @staticmethod
    async def add_address(user_id: int, address: str, nickname: Optional[str] = None) -> MonitorAddress:
        """
        为用户添加一个新的监听地址。
        在轮询架构下，这个函数只需要将数据存入数据库即可。
        """
        monitor_entry = await MonitorAddress.find_one(
            MonitorAddress.user_id == user_id,
            MonitorAddress.address == address
        )

        if monitor_entry:
            if nickname is not None:
                monitor_entry.nickname = nickname
                await monitor_entry.save()
        else:
            data_to_create = {"user_id": user_id, "address": address}
            if nickname is not None:
                data_to_create["nickname"] = nickname
            
            monitor_entry = MonitorAddress(**data_to_create)
            await monitor_entry.insert()
            
            # --- 不再需要调用任何注册函数 ---
            logging.info(f"新地址 {address} 已添加至数据库，等待后台监听任务扫描。")
            
        return monitor_entry

    @staticmethod
    async def delete_address(user_id: int, address: str) -> bool:
        """
        删除用户的一个监听地址。
        在轮询架构下，这个函数也只需要从数据库删除即可。
        """
        monitor_entry = await MonitorAddress.find_one(
            MonitorAddress.user_id == user_id,
            MonitorAddress.address == address
        )
        if not monitor_entry:
            return False
            
        await monitor_entry.delete()
        logging.info(f"地址 {address} 已从数据库移除，后台任务将不再扫描它 (如果无其他用户监听)。")
        return True

   # --- 辅助数据库查询方法 ---
    @staticmethod
    async def get_user_addresses(user_id: int) -> List[MonitorAddress]:
        """获取一个用户的所有监听地址。"""
        return await MonitorAddress.find(MonitorAddress.user_id == user_id).project(MonitorAddress).to_list()

    @staticmethod
    async def get_monitor_entry(user_id: int, address: str) -> Optional[MonitorAddress]:
        """获取单个监听地址的详细信息"""
        return await MonitorAddress.find_one(
            MonitorAddress.user_id == user_id,
            MonitorAddress.address == address
        )

    @staticmethod
    async def get_all_unique_addresses() -> List[str]:
        """获取数据库中所有被监听的、不重复的地址列表 (用于 Stream 同步)。"""
        return await MonitorAddress.distinct(MonitorAddress.address)

    @staticmethod
    async def get_users_monitoring_address(address: str) -> List[MonitorAddress]:
        """获取所有正在监听指定地址的用户条目 (用于通知分发)。"""
        return await MonitorAddress.find(MonitorAddress.address == address).to_list()

    @staticmethod
    async def toggle_setting(user_id: int, address: str, setting_name: str) -> Optional[MonitorAddress]:
        """切换指定地址的某项布尔设置（例如：收入提醒）。"""
        monitor_entry = await MonitoringService.get_monitor_entry(user_id, address)
        if monitor_entry and hasattr(monitor_entry, setting_name):
            current_value = getattr(monitor_entry, setting_name)
            setattr(monitor_entry, setting_name, not current_value)
            await monitor_entry.save()
            return monitor_entry
        return None

    @staticmethod
    async def update_nickname(user_id: int, address: str, nickname: str) -> Optional[MonitorAddress]:
        """更新地址的别名/备注"""
        monitor_entry = await MonitoringService.get_monitor_entry(user_id, address)
        if monitor_entry:
            monitor_entry.nickname = nickname
            await monitor_entry.save()
            return monitor_entry
        return None
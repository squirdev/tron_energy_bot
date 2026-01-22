import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict

from telegram.ext import Application
from pymongo.errors import DuplicateKeyError # 1. 导入 DuplicateKeyError 异常

from app.db.models import Order, OrderStatus, OrderType, StreamState
from app.services.tron_service import TronService
from app.services.energy_service import EnergyService
from app.core.config import settings
from app.bot.utils import PROCESSED_TX_CACHE_PAYMENT as PROCESSED_TX_CACHE, clear_expired_cache

PAYMENT_POLL_INTERVAL_SECONDS = 3

async def payment_polling_worker(ptb_app: Application):
    """
    后台轮询任务，用于监听收款地址并确认支付。
    增加了对数据库并发写入冲突的健壮处理。
    """
    logging.info("--- Payment Polling Worker Started ---")

    addresses_to_scan: Dict[str, str] = {
        settings.SPECIAL_OFFER_ADDRESS: "TRX"
    }

    while True:
        try:
            clear_expired_cache()
            now_utc = datetime.now(timezone.utc)
            
            expired_orders_result = await Order.find(
                Order.status == OrderStatus.PENDING_PAYMENT,
                Order.expires_at < now_utc
            ).update({"$set": {Order.status: OrderStatus.EXPIRED}})
            
            if expired_orders_result.modified_count > 0:
                logging.info(f"支付监听器清理了 {expired_orders_result.modified_count} 个过期订单。")

            for address, currency in addresses_to_scan.items():
                # --- 2. 使用更健壮的“查找或创建”逻辑 ---
                process_state = await StreamState.find_one(StreamState.address == address)
                
                if not process_state:
                    try:
                        last_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                        process_state = StreamState(address=address, last_processed_timestamp=last_timestamp)
                        await process_state.insert()
                        logging.info(f"为收款地址 {address[:10]}... 首次创建处理状态。")
                    except DuplicateKeyError:
                        logging.warning(f"为收款地址 {address[:10]}... 创建状态时发生竞争，将重新查询。")
                        process_state = await StreamState.find_one(StreamState.address == address)
                        if not process_state:
                            logging.error(f"在竞争后仍无法找到收款地址 {address[:10]} 的状态！")
                            continue

                last_timestamp = process_state.last_processed_timestamp
                
                query_timestamp = last_timestamp - 1000
                new_transactions = await TronService.get_new_transactions(address, query_timestamp)
                
                if not new_transactions:
                    continue
                
                latest_tx_timestamp_in_batch = last_timestamp

                for tx in new_transactions:
                    if tx.timestamp > last_timestamp and tx.tx_id not in PROCESSED_TX_CACHE:
                        logging.info(f"支付监听器发现新的、未处理的交易 {tx.tx_id}")
                        
                        PROCESSED_TX_CACHE[tx.tx_id] = datetime.now().timestamp()
                        
                        if tx.timestamp > latest_tx_timestamp_in_batch:
                            latest_tx_timestamp_in_batch = tx.timestamp

                        if tx.token_symbol == currency:
                            amount_buffer = 0.000001
                            matching_order = await Order.find_one(
                                Order.status == OrderStatus.PENDING_PAYMENT,
                                Order.currency == tx.token_symbol,
                                Order.expected_amount > tx.amount - amount_buffer,
                                Order.expected_amount < tx.amount + amount_buffer,
                            )

                            if matching_order:
                                matching_order.status = OrderStatus.PAID
                                matching_order.payment_txid = tx.tx_id
                                matching_order.paid_amount = tx.amount
                                matching_order.paid_at = datetime.utcnow()
                                await matching_order.save()
                                logging.info(f"订单 {matching_order.order_id} 支付成功！TxID: {tx.tx_id}")
                                
                                success_message = f"✅ 支付成功！\n您的订单({matching_order.order_type.value})已确认，正在为您处理..."
                                try:
                                    await ptb_app.bot.send_message(chat_id=matching_order.chat_id, text=success_message)
                                except Exception as e:
                                    logging.error(f"发送支付成功通知失败 (User: {matching_order.user_id}): {e}")
                                
                                # 将已支付的订单对象和 bot 实例传递给 EnergyService 进行处理
                                await EnergyService.process_paid_order(matching_order, ptb_app)
                                
                                break
                            else:
                                # --- 金额不匹配！ ---
                                # 在这里，我们可以查找是否有金额范围部分匹配的订单，
                                # 以便给用户更友好的提示。
                                # 例如，用户可能忘记了输入小数。
                                logging.warning(
                                    f"收到一笔金额为 {tx.amount} {tx.token_symbol} 的新交易 (TxID: {tx.tx_id[:10]}...), "
                                    f"但在待支付订单中找不到完全匹配的金额。"
                                )

                if latest_tx_timestamp_in_batch > last_timestamp:
                    process_state.last_processed_timestamp = latest_tx_timestamp_in_batch
                    await process_state.save()
                    logging.info(f"收款地址 {address[:10]} 的处理进度已更新至时间戳: {latest_tx_timestamp_in_batch}")
                
        except Exception as e:
            logging.error(f"支付轮询任务发生严重错误: {e}", exc_info=True)
        
        await asyncio.sleep(PAYMENT_POLL_INTERVAL_SECONDS)
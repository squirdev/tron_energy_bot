import asyncio
import logging
from datetime import datetime
from telegram.ext import Application
from pymongo.errors import DuplicateKeyError # 1. 导入 DuplicateKeyError 异常

from app.db.models import StreamState
from app.services.monitoring_service import MonitoringService
from app.services.tron_service import TronService
from app.bot.utils import PROCESSED_TX_CACHE_ADDRESS as PROCESSED_TX_CACHE, clear_expired_cache

LISTENER_POLL_INTERVAL_SECONDS = 6

async def address_listener_worker(ptb_app: Application):
    """
    后台轮询任务，用于监听所有用户添加的地址。
    增加了对数据库并发写入冲突的健壮处理。
    """
    logging.info("--- Address Listener Worker Started ---")

    while True:
        try:
            # 清理过期的内存缓存
            clear_expired_cache()

            unique_addresses = await MonitoringService.get_all_unique_addresses()
            if not unique_addresses:
                await asyncio.sleep(LISTENER_POLL_INTERVAL_SECONDS)
                continue
            
            logging.info(f"地址监听器正在检查 {len(unique_addresses)} 个地址...")

            for address in unique_addresses:
                # --- 2. 使用更健壮的“查找或创建”逻辑 ---
                process_state = await StreamState.find_one(StreamState.address == address)
                
                if not process_state:
                    # 如果数据库中不存在此地址的进度记录，我们尝试创建它
                    try:
                        last_timestamp = int((datetime.now().timestamp() - 300) * 1000)
                        process_state = StreamState(address=address, last_processed_timestamp=last_timestamp)
                        await process_state.insert()
                        logging.info(f"为地址 {address} 首次创建处理状态。")
                    except DuplicateKeyError:
                        # 如果在我们尝试插入的瞬间，payment_worker 已经抢先插入了，
                        # 那么 insert() 会失败。这没关系，我们只需要再查一次就能拿到它。
                        logging.warning(f"为地址 {address} 创建状态时发生竞争，将重新查询。")
                        process_state = await StreamState.find_one(StreamState.address == address)
                        if not process_state:
                            # 这种情况极少发生，但作为最终保险
                            logging.error(f"在竞争后仍无法找到地址 {address} 的状态！")
                            continue # 跳过此地址的本次处理

                # 从有效的 process_state 对象中获取时间戳
                last_timestamp = process_state.last_processed_timestamp
                
                # 为了安全，我们查询时可以稍微回退一点点时间
                query_timestamp = last_timestamp - 1000
                new_transactions = await TronService.get_new_transactions(address, query_timestamp)
                
                if new_transactions:
                    latest_tx_timestamp_in_batch = last_timestamp

                    for tx in new_transactions:
                        if tx.timestamp > last_timestamp and tx.tx_id not in PROCESSED_TX_CACHE:
                            logging.info(f"发现一笔新的、未处理过的交易 {tx.tx_id} for address {address}")
                            
                            if (datetime.now().timestamp() * 1000) - tx.timestamp > 3600 * 1000:
                                continue
                            
                            await MonitoringService.handle_webhook_transaction(tx)
                            
                            PROCESSED_TX_CACHE[tx.tx_id] = datetime.now().timestamp()
                            
                            if tx.timestamp > latest_tx_timestamp_in_batch:
                                latest_tx_timestamp_in_batch = tx.timestamp
                        else:
                            logging.debug(f"跳过已处理或过时的交易 {tx.tx_id} (Timestamp: {tx.timestamp})")

                    if latest_tx_timestamp_in_batch > last_timestamp:
                        process_state.last_processed_timestamp = latest_tx_timestamp_in_batch
                        await process_state.save()
                        logging.info(f"地址 {address} 的处理进度已更新至时间戳: {latest_tx_timestamp_in_batch}")

                await asyncio.sleep(1) 
                
        except Exception as e:
            logging.error(f"地址监听任务发生错误: {e}", exc_info=True)
        
        await asyncio.sleep(LISTENER_POLL_INTERVAL_SECONDS)
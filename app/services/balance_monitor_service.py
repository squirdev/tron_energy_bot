import logging
import asyncio
import httpx

from telegram.ext import Application

from app.core.config import settings

BALANCE_CHECK_INTERVAL_SECONDS = 15 * 60  # 15分钟


class BalanceMonitorService:
    """
    监控 kuaizu.io 账户余额，余额不足时通知管理员
    """
    KUAZU_BALANCE_API_URL = "https://api.kuaizu.io/api/balance"
    _low_balance_notified = False  # 标记是否已发送过低余额通知

    @staticmethod
    async def get_balance() -> float | None:
        """查询 kuaizu.io 账户余额"""
        payload = {"apiKey": settings.KUAZU_API_KEY}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    BalanceMonitorService.KUAZU_BALANCE_API_URL, json=payload
                )
                response.raise_for_status()
                result = response.json()

            if result.get("code") == 1:
                balance = float(result.get("data", {}).get("balance", 0))
                logging.info(f"kuaizu.io 账户余额: {balance}")
                return balance
            else:
                logging.error(
                    f"查询余额失败。Code: {result.get('code')}, Msg: {result.get('msg')}"
                )
                return None

        except httpx.HTTPStatusError as e:
            logging.error(f"查询余额时发生 HTTP 错误: {e.response.status_code}")
            return None
        except Exception as e:
            logging.error(f"查询余额时发生未知错误: {e}", exc_info=True)
            return None


async def balance_monitor_worker(ptb_app: Application):
    """
    后台任务，定期检查 kuaizu.io 余额，余额不足时通知管理员（仅通知一次）
    """
    logging.info("--- Balance Monitor Worker Started ---")

    while True:
        try:
            balance = await BalanceMonitorService.get_balance()

            if balance is not None:
                if balance < settings.KUAZU_BALANCE_THRESHOLD:
                    # 余额不足，且还未发送过通知
                    if not BalanceMonitorService._low_balance_notified:
                        warning_message = (
                            f"⚠️ 余额不足警告\n\n"
                            f"kuaizu.io 账户余额: {balance:.2f}\n"
                            f"告警阈值: {settings.KUAZU_BALANCE_THRESHOLD:.2f}\n\n"
                            f"请及时充值！"
                        )
                        try:
                            await ptb_app.bot.send_message(
                                chat_id=settings.ADMIN_CHAT_ID, text=warning_message
                            )
                            BalanceMonitorService._low_balance_notified = True
                            logging.warning(f"已向管理员发送余额不足警告，当前余额: {balance}")
                        except Exception as e:
                            logging.error(f"发送余额警告消息失败: {e}")
                else:
                    # 余额充足，重置标记以便下次不足时能再次发送
                    if BalanceMonitorService._low_balance_notified:
                        logging.info(f"余额已恢复至 {balance:.2f}，重置低余额通知标记")
                        BalanceMonitorService._low_balance_notified = False

        except Exception as e:
            logging.error(f"余额监控任务发生错误: {e}", exc_info=True)

        await asyncio.sleep(BALANCE_CHECK_INTERVAL_SECONDS)

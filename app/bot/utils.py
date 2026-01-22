import logging
from datetime import datetime
from typing import Callable, Awaitable, Optional
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode


# 支付监听缓存（用于 payment_polling_worker）
PROCESSED_TX_CACHE_PAYMENT: dict[str, float] = {}

# 用户地址监听缓存（用于 address_listener_worker）
PROCESSED_TX_CACHE_ADDRESS: dict[str, float] = {}

CACHE_EXPIRATION_SECONDS = 60 * 5 # 缓存有效期5分钟

def clear_expired_cache():
    """清理两个缓存中的过期交易ID"""
    now = datetime.now().timestamp()

    def _clear(cache: dict[str, float], name: str):
        expired_txs = [tx_id for tx_id, ts in cache.items() if now - ts > CACHE_EXPIRATION_SECONDS]
        for tx_id in expired_txs:
            try:
                del cache[tx_id]
            except KeyError:
                pass
        if expired_txs:
            logging.debug(f"清理了 {len(expired_txs)} 个过期的缓存 TX ID ({name})。")

    _clear(PROCESSED_TX_CACHE_PAYMENT, "payment")
    _clear(PROCESSED_TX_CACHE_ADDRESS, "address")
    
def clear_pending_actions(context: ContextTypes.DEFAULT_TYPE):
    """一个辅助函数，用于清除所有待处理的文本输入状态。"""
    if 'next_action' in context.user_data:
        del context.user_data['next_action']

async def reply(update: Update, text: str, parse_mode: str = ParseMode.HTML, **kwargs):
    """
    统一回复工具。
    - 自动引用消息（如果适用）。
    - 默认使用 HTML 解析模式，但可以被覆盖。
    """
    if update.message:
        return await update.message.reply_text(
            text=text,
            parse_mode=parse_mode,
            reply_to_message_id=update.message.message_id,
            **kwargs
        )
    elif update.effective_chat:
        return await update.effective_chat.send_message(
            text=text, 
            parse_mode=parse_mode,
            **kwargs
        )

async def cancel_conversation(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    # --- 新增：一个可选的、可异步调用的“后续”函数 ---
    follow_up_action: Optional[Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]] = None
) -> int:
    """
    通用取消函数，清理用户数据，结束会话，并可选地执行一个后续动作。
    """
    context.user_data.clear()
    
    await update.message.reply_text("操作已取消。")
    
    # 如果提供了后续动作函数，则执行它
    if follow_up_action:
        await follow_up_action(update, context)
    
    return ConversationHandler.END

async def cleanup_order_message(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue 的回调函数，用于清理过期的消息。"""
    job = context.job
    chat_id = job.data['chat_id']
    message_id = job.data['message_id']

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logging.info(f"成功删除过期的消息 {message_id} in chat {chat_id}")
    except Exception as e:
        logging.warning(f"清理过期的消息 {message_id} 失败: {e}")

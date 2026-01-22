import logging
import textwrap
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ApplicationHandlerStop,
)
from telegram.constants import ParseMode

from app.bot import constants as const
from app.bot.utils import clear_pending_actions, reply, cancel_conversation
from app.services.tron_service import TronService
from app.bot.keyboards import build_monitor_this_address_keyboard

# --- "钱包查询" 会话 ---

# 1. 定义会话状态
RECEIVE_QUERY_ADDRESS = range(30, 31) # 使用新的独立范围

# 2. 会话入口和状态处理函数

async def handle_wallet_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """(入口) 处理 "🔎钱包查询" 按钮，请求用户发送地址并进入会话状态"""
    clear_pending_actions(context)
    
    text = "请发送您需要监听或查询的trc20地址"
    await reply(update, text, parse_mode="Markdown")

    # 进入等待地址的状态
    return RECEIVE_QUERY_ADDRESS

async def wallet_query_address_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """(状态1) 接收到地址，进行查询或提示错误"""
    
    address = update.message.text.strip()
    
    if not address.startswith("T") or len(address) != 34:
        await reply(update, "地址格式不正确，请输入一个T开头的TRON地址。")
        # --- 关键修改：保持在当前状态，继续等待用户输入 ---
        return RECEIVE_QUERY_ADDRESS

    # 地址格式正确，开始查询
    wait_message = await reply(update, f"正在查询地址 `{address}` 的信息...", parse_mode="Markdown")
    details = await TronService.get_account_details(address)

    if details:
        active_time_str = details.last_operation_time.strftime("%Y-%m-%d %H:%M:%S")
        create_time_str = details.creation_time.strftime("%Y-%m-%d %H:%M:%S")
        query_result_text = textwrap.dedent(f"""
        `{details.address}`
        ——————————资源——————————
        TRX余额:{details.trx_balance}
        USDT余额:{details.usdt_balance}
        能量: {details.energy_used} / {details.energy_limit}
        质押资产: {details.total_staked}
        免费带宽: {details.net_used} / {details.net_limit}
        质押带宽: {details.staked_bandwidth_used} / {details.staked_bandwidth_limit}
        活跃时间: {active_time_str}
        创建时间: {create_time_str}
        """)
        keyboard = build_monitor_this_address_keyboard(address)
        await wait_message.edit_text(query_result_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await wait_message.edit_text("查询失败，地址可能未激活或网络错误。")

    # --- 关键修改：查询成功后，结束会话 ---
    return ConversationHandler.END

# 3. 创建并导出 ConversationHandler 实例
# 注意：这个会话的入口比较特殊，它是由一个 MessageHandler 触发的
wallet_query_conv_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Text([const.BTN_WALLET_QUERY]), handle_wallet_query)
    ],
    states={
        RECEIVE_QUERY_ADDRESS: [
            # 在这个状态下，我们等待用户发送任何文本消息
            MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_query_address_received)
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel_conversation)
    ],
    per_message=False
)

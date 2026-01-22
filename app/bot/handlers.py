import logging
import textwrap
import functools
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ApplicationHandlerStop,
)
from telegram.constants import ParseMode

from app.bot import keyboards
from app.bot import constants as const
from app.core.config import settings
from app.bot.utils import clear_pending_actions, reply, cancel_conversation
from app.services.monitoring_service import MonitoringService
from app.bot.keyboards import build_monitor_this_address_keyboard
from app.services.tron_service import TronService, TronAccountDetails


# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /start 命令，发送欢迎消息和主菜单
    """

    await update.message.reply_text(
        text=const.WELCOME_TEXT, reply_markup=keyboards.get_main_keyboard()
    )

# --- 监听列表功能处理器 ---

# 状态定义 (用于添加地址和设置备注的会话)
(ASK_ADDRESS, ASK_NICKNAME_FOR_NEW, ASK_NICKNAME_FOR_EXISTING) = range(3)


async def handle_monitor_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    处理 "🛎️监听列表" 按钮
    """
    clear_pending_actions(context)

    user_id = update.effective_user.id
    addresses = await MonitoringService.get_user_addresses(user_id)

    if not addresses:
        # 如果列表为空，只发送提示文本
        text = "你没有绑定过监听地址"
        await reply(update, text)
        return

    # 如果列表不为空，显示带有按钮的列表 (逻辑保持不变)
    text = f"已添加地址共 {len(addresses)} 个\n点击按钮可对地址进行操作"
    keyboard = keyboards.build_monitor_list_keyboard(addresses)
    await reply(update, text, reply_markup=keyboard, parse_mode="Markdown")
    raise ApplicationHandlerStop


async def show_monitoring_list_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """
    处理内联键盘的回调，用于返回并显示地址列表 (第一层)
    """
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    addresses = await MonitoringService.get_user_addresses(user_id)

    text = f"已添加地址共 {len(addresses)} 个\n\n点击下方对应按钮可进行操作。"
    if not addresses:
        text = "您的监听列表是空的。\n点击下方“➕ 添加新地址”按钮来添加一个吧！"

    keyboard = keyboards.build_monitor_list_keyboard(addresses)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_monitor_actions_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """回调：显示地址操作选项 (第二层)"""
    query = update.callback_query
    await query.answer()

    address = query.data.split(":")[1]
    text = f"请对地址\n`{address}`\n进行操作"
    keyboard = keyboards.build_monitor_actions_keyboard(address)

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_monitor_settings_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """回调：显示详细设置 (第三层)"""
    query = update.callback_query
    await query.answer()

    address = query.data.split(":")[1]
    user_id = update.effective_user.id

    monitor_entry = await MonitoringService.get_monitor_entry(user_id, address)
    if not monitor_entry:
        await query.edit_message_text("错误：找不到该地址。可能已被删除。")
        return

    text = f"正在设置地址: `{address}`\n请选择以下功能进行下一步"
    keyboard = keyboards.build_monitor_settings_keyboard(monitor_entry)

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def toggle_monitor_setting_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """回调：切换设置 (例如：✅ -> ❌)"""
    query = update.callback_query

    _, address, setting_name = query.data.split(":")
    user_id = update.effective_user.id

    updated_entry = await MonitoringService.toggle_setting(
        user_id, address, setting_name
    )

    if updated_entry:
        await query.answer(text="设置已更新")
        text = f"正在设置地址: `{address}`\n请选择以下功能进行下一步"
        keyboard = keyboards.build_monitor_settings_keyboard(updated_entry)
        await query.edit_message_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    else:
        await query.answer(text="操作失败！", show_alert=True)


async def delete_monitor_address_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """回调：删除地址确认"""
    query = update.callback_query
    address_to_delete = query.data.split(":")[1]
    user_id = update.effective_user.id

    success = await MonitoringService.delete_address(user_id, address_to_delete)

    if success:
        await query.answer(
            text=f"地址 {address_to_delete[:8]}... 已移除", show_alert=True
        )
    else:
        await query.answer(text="移除失败，地址不存在", show_alert=True)

    # 刷新列表
    await show_monitoring_list_callback(update, context)


# --- 添加地址/设置备注的 Conversation Handlers ---
async def add_address_start_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """会话入口：请求用户输入地址"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "好的，请发送您想要监听的TRON钱包地址（T开头）：\n\n发送 /cancel 可以取消操作。"
    )
    return ASK_ADDRESS


async def ask_address_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收地址，并请求输入别名"""
    address = update.message.text.strip()
    if not address.startswith("T") or len(address) != 34:
        await update.message.reply_text(
            "地址格式不正确，请重新发送一个T开头的TRON地址。"
        )
        return ASK_ADDRESS

    context.user_data["new_monitor_address"] = address
    await update.message.reply_text(
        "很好！现在给这个地址起一个备注/别名吧（例如：主钱包），方便您识别。\n\n如果您不想设置，请发送 /skip"
    )
    return ASK_NICKNAME_FOR_NEW


async def ask_nickname_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收新地址的别名，并保存到数据库"""
    nickname = update.message.text.strip()
    address = context.user_data["new_monitor_address"]
    user_id = update.effective_user.id

    await MonitoringService.add_address(
        user_id=user_id, address=address, nickname=nickname
    )
    await update.message.reply_text(
        f"✅ 地址 `{address}` (备注: {nickname}) 已成功添加！", parse_mode="Markdown"
    )

    del context.user_data["new_monitor_address"]
    await handle_monitor_list(update, context)  # 显示更新后的列表
    return ConversationHandler.END


async def skip_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户跳过为新地址设置别名"""
    address = context.user_data["new_monitor_address"]
    user_id = update.effective_user.id

    await MonitoringService.add_address(
        user_id=user_id, address=address
    )  # 使用模型中的默认备注
    await update.message.reply_text(
        f"✅ 地址 `{address}` 已成功添加！", parse_mode="Markdown"
    )

    del context.user_data["new_monitor_address"]
    await handle_monitor_list(update, context)
    return ConversationHandler.END


async def set_nickname_start_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """会话入口：请求用户为已有地址输入新备注"""
    query = update.callback_query
    await query.answer()
    address = query.data.split(":")[1]
    context.user_data["address_to_update"] = address
    await query.edit_message_text(
        f"请输入地址 `{address}` 的新备注：\n\n发送 /cancel 可以取消。",
        parse_mode="Markdown",
    )
    return ASK_NICKNAME_FOR_EXISTING


async def existing_nickname_received(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """接收已有地址的新备注并更新"""
    nickname = update.message.text.strip()
    address = context.user_data["address_to_update"]
    user_id = update.effective_user.id

    updated_entry = await MonitoringService.update_nickname(user_id, address, nickname)
    if updated_entry:
        await update.message.reply_text(f"✅ 备注已更新为: {nickname}")
        # 重新显示设置界面
        text = f"正在设置地址: `{address}`\n请选择以下功能进行下一步"
        keyboard = keyboards.build_monitor_settings_keyboard(updated_entry)
        await update.message.reply_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("更新失败！")

    del context.user_data["address_to_update"]
    return ConversationHandler.END

# 将所有会话处理器组合起来
monitor_conv_handler = ConversationHandler(
    entry_points=[
        # 入口1：处理 "➕ 添加新地址" 按钮点击
        CallbackQueryHandler(
            add_address_start_callback, pattern="^add_monitor_address$"
        ),
        # 入口2 处理 "📝 设置备注" 按钮点击
        CallbackQueryHandler(set_nickname_start_callback, pattern="^set_nickname:"),
    ],
    states={
        # 状态：等待用户发送新地址
        ASK_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_address_received)
        ],
        # 状态：等待用户为新地址输入备注
        ASK_NICKNAME_FOR_NEW: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_nickname_received),
            CommandHandler("skip", skip_nickname),
        ],
        # 状态：等待用户为已有地址输入新备注
        ASK_NICKNAME_FOR_EXISTING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, existing_nickname_received)
        ],
    },
    # --- 在这里添加所有主菜单按钮作为 fallbacks ---
    fallbacks=[
        # 使用 functools.partial 来包装 cancel_conversation
        CommandHandler(
            "cancel",
            functools.partial(
                cancel_conversation, follow_up_action=handle_monitor_list
            ),
        )
    ],
    # 允许用户通过点击其他按钮或发送命令来提前结束会话
    per_message=False,
)


# --- 处理 "监听该地址" 按钮的回调 ---
async def monitor_this_address_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """
    处理来自钱包查询结果的 "监听该地址" 按钮点击。
    """
    query = update.callback_query

    address_to_monitor = query.data.split(":")[1]
    user_id = update.effective_user.id

    # 检查地址是否已存在，避免重复添加
    existing_entry = await MonitoringService.get_monitor_entry(
        user_id, address_to_monitor
    )
    if existing_entry:
        await query.answer(text="⚠️ 该地址已在您的监听列表中！", show_alert=True)
        return

    # 添加地址
    await MonitoringService.add_address(user_id=user_id, address=address_to_monitor)
    await query.answer(text="✅ 已成功添加至监听列表！", show_alert=True)

    # 移除消息上的键盘，表示操作已完成
    await query.edit_message_reply_markup(reply_markup=None)

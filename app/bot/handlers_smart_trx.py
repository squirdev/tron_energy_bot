import logging
import textwrap
import random
import functools
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
    ApplicationHandlerStop,
)
from telegram.constants import ParseMode

# 导入项目内的其他模块
from app.bot import keyboards
from app.bot.utils import clear_pending_actions, reply, cancel_conversation
from app.bot import constants as const
from app.core.config import settings
from app.bot.utils import cleanup_order_message
from app.db.models import Order, OrderType, OrderStatus

# --- "智能笔数" 购买会话 ---

# 定义会话状态
RECEIVE_SMART_TRX_ADDRESS = range(20, 21)  # 使用独立的范围避免冲突

# 会话入口和状态处理函数
async def handle_smart_trx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """(入口) 处理 "智能笔数" 按钮，显示说明和套餐选择键盘"""
    clear_pending_actions(context)

    price_trx = settings.ENERGY_SMART_PRICE
    price_usdt = settings.ENERGY_SMART_PRICE_USDT

    response_text = textwrap.dedent(
        f"""
        💠单价: {price_usdt:.2f} USDT 或 {price_trx:.2f} TRX/每笔
        🔸按笔数计费的能量租用方式。开启后匹配131000的能量
        🔸每笔发送65000K能量是一笔, 每笔发送131000能量是扣2笔
        ✅适合每天有1笔以上转账次数的人, 高频交易不会转错trx。
        🔸不限时, 24小时内有一笔以上转账, 不额外扣费!
        1.24小时内未转账, 会扣除131000能量的2笔占用费。
        2.长时间不转账, 可以在地址列表关闭笔数套餐
        
        - - - - - - - - - - - -
        发送 /start 可以更新最新功能列表
        以下按钮可以选择不同的笔数套餐方案:
    """
    )

    keyboard = keyboards.build_smart_trx_packages_keyboard()
    await reply(update, response_text, reply_markup=keyboard)
    raise ApplicationHandlerStop


async def smart_trx_size_selected(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """(入口) 用户选择了笔数套餐，现在请求输入接收地址"""
    query = update.callback_query
    
    try:
        await query.answer()
        
        size = int(query.data.split(":")[1])
        context.user_data["smart_trx_size"] = size

        price_trx = settings.ENERGY_SMART_PRICE
        price_usdt = settings.ENERGY_SMART_PRICE_USDT
        total_trx = size * price_trx
        total_usdt = size * price_usdt

        text = textwrap.dedent(
            f"""
            ✅ 您选择了 **{size}笔** 套餐
            
            💰 价格信息：
            • TRX: {total_trx:.2f} TRX ({price_trx:.2f} TRX/笔)
            • USDT: {total_usdt:.2f} USDT ({price_usdt:.2f} USDT/笔)
            
            📝 请输入能量接收地址（请确认地址已激活）：
            
            💡 提示：发送 /cancel 可以取消订单
            """
        )

        try:
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as edit_error:
            # 如果编辑消息失败（例如消息太旧），发送新消息
            logging.warning(f"编辑消息失败，改为发送新消息: {edit_error}")
            try:
                await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            except Exception as reply_error:
                logging.error(f"发送新消息也失败: {reply_error}")
                await query.answer("❌ 操作失败，请重试", show_alert=True)
                return ConversationHandler.END
        
        logging.info(f"用户 {update.effective_user.id} 选择了 {size}笔 套餐，等待输入地址")
        return RECEIVE_SMART_TRX_ADDRESS
        
    except Exception as e:
        logging.error(f"处理智能笔数套餐选择时出错: {e}", exc_info=True)
        try:
            await query.answer("❌ 处理失败，请重试", show_alert=True)
            await query.edit_message_text("❌ 处理失败，请重新选择套餐。")
        except:
            pass
        return ConversationHandler.END


async def smart_trx_address_received(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """(状态1) 接收到地址，生成订单信息并结束会话"""
    receiver_address = update.message.text.strip()

    if not receiver_address.startswith("T") or len(receiver_address) != 34:
        await update.message.reply_text(
            "❌ 地址格式不正确，请重新发送一个T开头的TRON地址（34个字符）。\n\n"
            "💡 提示：发送 /cancel 可以取消订单"
        )
        return RECEIVE_SMART_TRX_ADDRESS
    
    logging.info(f"用户 {update.effective_user.id} 输入了接收地址: {receiver_address[:10]}...")

    size = context.user_data["smart_trx_size"]

    await generate_and_send_order_message(
        update, context, size, receiver_address, "USDT"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def generate_and_send_order_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    size: int,
    receiver_address: str,
    currency: str,
    is_edit: bool = False,
):
    """一个辅助函数，用于生成和发送/编辑订单消息"""
    price_per_trx = settings.ENERGY_SMART_PRICE
    price_per_usdt = settings.ENERGY_SMART_PRICE_USDT

    total_amount = 0
    if currency == "TRX":
        # random_suffix = random.randint(1000, 9999) / 10000.0
        # total_amount = (size * price_per_trx) + random_suffix
        total_amount = size * price_per_trx
        price_per_unit_str = f"{price_per_trx:.2f} TRX"
        total_amount_str = f"{total_amount:.4f}"
        currency_unit = "TRX"
    else:  # USDT
        random_suffix = random.randint(1000, 9999) / 10000.0
        total_amount = (size * price_per_usdt) + random_suffix
        price_per_unit_str = f"{price_per_usdt:.2f} USDT"
        total_amount_str = f"{total_amount:.4f}"
        currency_unit = "USDT"

    payment_address = settings.ENERGY_SMART_ADDRESS
    expiration_time = datetime.utcnow() + timedelta(minutes=30)
    expiration_str = expiration_time.strftime("%Y-%m-%d %H:%M:%S")

    order_id = f"smart_{update.effective_user.id}_{int(datetime.now().timestamp())}"

    # Save order to database for payment detection
    try:
        new_order = Order(
            order_id=order_id,
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            order_type=OrderType.SMART_TRX,
            currency=currency,
            expected_amount=total_amount,
            expires_at=expiration_time,
            details={
                "size": size,
                "receiver_address": receiver_address,
                "trx_amount": size * price_per_trx,
                "usdt_amount": size * price_per_usdt
            }
        )
        await new_order.insert()
        logging.info(f"创建智能笔数订单 {order_id}: {size}笔, {currency}, {total_amount}")
    except Exception as e:
        logging.error(f"保存智能笔数订单失败: {e}", exc_info=True)
        # Continue anyway, but payment detection won't work

    # Also store in context for currency switching
    context.chat_data[order_id] = {
        "size": size,
        "receiver_address": receiver_address,
        "trx_amount": size * price_per_trx,
        "usdt_amount": size * price_per_usdt
    }

    # 能量代理地址：<code>{receiver_address}</code>
    response_text = textwrap.dedent(
        f"""
        每笔单价：{price_per_unit_str}
        收款金额：<code>{total_amount_str}</code> {currency_unit}(点击复制)
        使用笔数：{size} 笔转账

        收款trc20地址为：
        <code>{payment_address}</code>
        (点击地址自动复制)

        订单将于 {expiration_str} 过期，请尽快支付！
    """
    )

    keyboard = keyboards.build_smart_trx_order_keyboard(order_id, currency)

    if is_edit:
        query = update.callback_query
        await query.edit_message_text(
            response_text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
    else:
        await update.message.reply_html(text=response_text, reply_markup=keyboard)


# --- 订单操作的回调处理器 (独立于会话) ---
async def switch_currency_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """处理切换支付币种的按钮"""
    query = update.callback_query
    await query.answer()

    _, order_id, new_currency = query.data.split(":")

    # Try to get order data from database first, fallback to context
    order = await Order.find_one(Order.order_id == order_id)
    if order and order.status == OrderStatus.PENDING_PAYMENT:
        order_data = {
            "size": order.details.get("size"),
            "receiver_address": order.details.get("receiver_address"),
            "trx_amount": order.details.get("trx_amount"),
            "usdt_amount": order.details.get("usdt_amount")
        }
        # Update order currency and amount in database
        price_per_trx = settings.ENERGY_SMART_PRICE
        price_per_usdt = settings.ENERGY_SMART_PRICE_USDT
        size = order_data["size"]
        
        if new_currency == "TRX":
            new_amount = size * price_per_trx
        else:  # USDT
            random_suffix = random.randint(1000, 9999) / 10000.0
            new_amount = (size * price_per_usdt) + random_suffix
        
        order.currency = new_currency
        order.expected_amount = new_amount
        await order.save()
        logging.info(f"订单 {order_id} 切换币种为 {new_currency}, 新金额: {new_amount}")
    else:
        # Fallback to context data
        order_data = context.chat_data.get(order_id)
        if not order_data:
            await query.edit_message_text("订单信息已过期，请重新发起购买。")
            return

    await generate_and_send_order_message(
        update,
        context,
        order_data["size"],
        order_data["receiver_address"],
        new_currency,
        is_edit=True,
    )


#  创建并导出 ConversationHandler 实例
smart_trx_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(smart_trx_size_selected, pattern="^smart_trx_size:"),
    ],
    states={
        RECEIVE_SMART_TRX_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, smart_trx_address_received)
        ],
    },
    fallbacks=[
        CommandHandler(
            "cancel",
            functools.partial(cancel_conversation, follow_up_action=handle_smart_trx),
        )
    ],
    per_message=False,
)

# --- 取消订单的回调处理器 ---
async def cancel_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理“取消订单”按钮点击，直接删除该消息。"""
    query = update.callback_query
    
    # 向 Telegram API 发送一个确认，表示我们已经收到了回调
    # 这会让按钮上的“加载中”状态消失
    await query.answer()
    
    # --- 删除这条消息 ---
    try:
        await query.message.delete()
        logging.info(f"用户 {update.effective_user.id} 取消并删除了订单消息。")
    except Exception as e:
        # 如果消息因为某些原因（例如，消息太旧，或者机器人权限不足）无法删除，
        # 我们只记录一个警告，而不会让程序崩溃。
        logging.warning(f"删除订单消息失败: {e}")
        # 也可以选择编辑消息文本，告知用户操作完成
        # await query.edit_message_text("订单已取消。")

import logging
import textwrap
import random 
from datetime import datetime, timedelta 
from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

# 导入通用辅助函数和配置
from app.bot.utils import clear_pending_actions, reply
from app.core.config import settings
from app.bot.keyboards import build_monitor_this_address_keyboard
from app.services.tron_service import TronService
from app.bot.utils import cleanup_order_message
from app.db.models import Order, OrderType, OrderStatus
from app.bot import keyboards 

# --- 主菜单按钮处理器 ---

# --- 处理 "15分钟特价能量" 按钮 ---

async def handle_special_offer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """处理 "🔥15分钟特价能量🔥" 按钮，会检查并复用已存在的待支付订单"""
    clear_pending_actions(context)
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    payment_address = getattr(settings, 'SPECIAL_OFFER_ADDRESS', 'TRS1XXAEx3dnTMufsUXunqWNmdEhrp1Zd')
    order_duration_minutes = 10 # 订单有效期

    price_trx = settings.SPECIAL_OFFER_PRICE # 基础价格

    try:
        # --- 在创建前先查找 ---
        existing_order = await Order.find_one(
            Order.user_id == user_id,
            Order.order_type == OrderType.SPECIAL_OFFER,
            Order.status == OrderStatus.PENDING_PAYMENT,
            Order.expires_at > datetime.utcnow() # 确保订单还未过期
        )

        if existing_order:
            # --- 如果找到了已存在的待支付订单 ---
            logging.info(f"为用户 {user_id} 找到了已存在的特价能量订单 {existing_order.order_id}，正在重新发送。")
            
            expected_amount = existing_order.expected_amount
            expiration_str = existing_order.expires_at.strftime('%Y-%m-%d %H:%M:%S')
            
            # 构建“提醒”性质的文案
            response_text = textwrap.dedent(f"""
                🔥您有一个未支付的15分钟特价能量订单🔥

                请继续支付 <code>{expected_amount:.5f}</code> TRX 到下方地址，能量将自动充值到您的**付款地址**。

                收款地址:
                <code>{payment_address}</code>
                (点击地址自动复制)

                <b>注意:</b> 
                ‼️请务必核对金额尾数，金额不对则无法确认
                ‼️请务必核对金额尾数，金额不对则无法确认
                ‼️请务必核对金额尾数，金额不对则无法确认
                订单将于 {expiration_str} 过期，请尽快支付！
            """)
        
        else:
            # --- 如果没有找到，才创建新订单 (这是您之前的逻辑) ---
            random_suffix = random.randint(100, 999) / 100000.0
            expected_amount = price_trx + random_suffix
            
            new_order = Order(
                user_id=user_id,
                chat_id=chat_id,
                order_type=OrderType.SPECIAL_OFFER,
                currency="TRX",
                expected_amount=expected_amount,
                expires_at=datetime.utcnow() + timedelta(minutes=order_duration_minutes),
                # details 为空，因为接收地址将是付款地址
            )
            await new_order.insert()
            logging.info(f"为用户 {user_id} 创建了新的特价能量订单 {new_order.order_id}")
            
            # 构建“创建成功”的文案
            response_text = textwrap.dedent(f"""

            ✅正在创建支付订单.........

            请支付 <code>{expected_amount:.5f}</code> TRX = 免费一笔能量
            给交易所地址转账也不会扣手续费

            下单地址:
            <code>{payment_address}</code>
            (点击地址自动复制)

            <b>注意:</b> 
            ‼️请务必核对金额尾数，金额不对则无法确认
            ‼️请务必核对金额尾数，金额不对则无法确认
            ‼️请务必核对金额尾数，金额不对则无法确认
            请在{order_duration_minutes}分钟内完成购买，超时将自动取消订单
        """)
        
        # 统一发送消息
        await reply(update, response_text)

    except Exception as e:
        logging.error(f"处理特价能量订单时失败: {e}", exc_info=True)
        await reply(update, "订单处理失败，请稍后再试或联系客服。")
    
    raise ApplicationHandlerStop

async def handle_energy_rent(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """处理 "能量闪租" 按钮"""
    clear_pending_actions(context)
    payment_address = settings.ENERGY_FLASH_ADDRESS

    base_price = settings.ENERGY_FLASH_PRICE
    
    # 计算不同套餐的价格
    price_1_unit = base_price * 1
    price_2_units = base_price * 2
    price_3_units = base_price * 3
    price_4_units = base_price * 4
    price_5_units = base_price * 5
    response_text = textwrap.dedent(
        f"""
        🌈使用能量可节省 80% 转U手续费

        🔹1笔对方地址【有U】 {price_1_unit:.3f} TRX  (1小时有效)
        🔹1笔对方地址【无U】 {price_2_units:.3f} TRX  (1小时有效)

        🔥时效套餐（一小时过期）🔥
        🔋转账 {price_1_unit:.3f} TRX = 免费1笔转账
        🔋转账 {price_2_units:.3f} TRX = 免费2笔转账
        🔋转账 {price_3_units:.3f} TRX = 免费3笔转账
        🔋转账 {price_4_units:.3f} TRX = 免费4笔转账
        🔋转账 {price_5_units:.3f} TRX = 免费5笔转账

        📣转 TRX 到下方地址，能量自动到账

        <code>{payment_address}</code>
        (点击地址复制)

        ✅全自动到账，默认返回原地址
        <b>注意:</b> 
        1. 向无U的地址转账, 需要双倍的能量。
        2. 小时套餐请在1小时内使用能量，否则会过期回收。
        3. 必须按照指定金额租用，否则会租用失败。
        🚫请勿使用交易所或中心化钱包转账
    """
    )
    await reply(update, response_text)
    raise ApplicationHandlerStop


async def handle_trx_exchange(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """处理 "TRX兑换" 按钮"""
    clear_pending_actions(context)
    exchange_address = settings.TRX_EXCHANGE_ADDRESS
    rate = settings.TRX_EXCHANGE_PRICE # 您可以替换为真实的汇率服务调用
    rate_for_100_usdt = f"{100 * rate:.2f}"
    
    response_text = textwrap.dedent(
        f"""
        💹实时汇率: 100 USDT = {rate_for_100_usdt} TRX

        往🔻下方地址转USDT,会5秒内自动回你TRX
        <code>{exchange_address}</code>
        (点击地址自动复制)

        1️⃣进U即兑,全自动返TRX,1U起兑
        2️⃣不要使用交易所转账，丢失自负

        💰 如果TRX余额不足以转帐,可在机器人 @TRXnengliang66_bot 内自助预支一次转账用的TRX能量矿工费或者找客服索要！！！

        有任何问题,请私聊联系老板,双向用户可以私聊机器人
    """
    )
    keyboard = keyboards.build_customer_service_keyboard()
    await reply(update, response_text, reply_markup=keyboard)
    raise ApplicationHandlerStop


async def handle_standard_energy(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """处理 "次数能量" 按钮"""
    clear_pending_actions(context)
    payment_address = settings.ENERGY_STANDARD_ADDRESS
    payment_price = settings.ENERGY_STANDARD_PRICE
    response_text = textwrap.dedent(
        f"""
    🔴次数套餐🔴（无时间限制）
    （24小时不使用，则扣一笔占用费）

    🔴一笔转账 = {payment_price:.3f} TRX  
    （直接转账自动秒发货，单笔最高可购1万笔）  
    <code>{payment_address}</code>  

    🔴对方有U 没U 都是扣除一笔转账
    """
    )
    await reply(update, response_text)
    raise ApplicationHandlerStop

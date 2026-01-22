from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from app.bot import constants as const
from app.db.models import MonitorAddress
from typing import List
from app.core.config import settings

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    创建并返回主菜单的ReplyKeyboard
    """
    keyboard = [
        [const.BTN_SPECIAL_OFFER],
        [const.BTN_WALLET_QUERY, const.BTN_ENERGY_RENT, const.BTN_TRX_EXCHANGE, ],
        [const.BTN_MONITOR_LIST, const.BTN_SMART_TRX, const.BTN_TRUE_TRX],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def get_status_emoji(status: bool) -> str:
    """根据布尔值返回对应的emoji"""
    return "✅" if status else "❌"


def build_monitor_list_keyboard(
    addresses: List[MonitorAddress],
) -> InlineKeyboardMarkup:
    """
    构建第一层：地址列表
    """
    keyboard = []
    # 使用 enumerate 来创建带序号的按钮
    for i, item in enumerate(addresses):
        # 如果有备注，优先显示备注，否则显示地址
        label = f"{i + 1}. {item.nickname if item.nickname != '未设置备注' else item.address[:6] + '...' + item.address[-4:]}"
        callback_data = f"monitor_actions:{item.address}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])

    keyboard.append(
        [InlineKeyboardButton("➕ 添加新地址", callback_data="add_monitor_address")]
    )
    # keyboard.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]) # 返回由物理键盘处理
    return InlineKeyboardMarkup(keyboard)


def build_monitor_actions_keyboard(address: str) -> InlineKeyboardMarkup:
    """
    构建第二层：操作选择 (修改设置 / 删除)
    """
    keyboard = [
        [InlineKeyboardButton("修改设置", callback_data=f"monitor_settings:{address}")],
        [InlineKeyboardButton("删除监控", callback_data=f"delete_monitor:{address}")],
        [InlineKeyboardButton("<< 返回钱包列表", callback_data="show_monitoring_list")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_monitor_settings_keyboard(
    monitor_entry: MonitorAddress,
) -> InlineKeyboardMarkup:
    """
    构建第三层：详细设置
    """
    address = monitor_entry.address
    keyboard = [
        [
            InlineKeyboardButton(
                f"收入提醒 {get_status_emoji(monitor_entry.notify_on_incoming)}",
                callback_data=f"toggle:{address}:notify_on_incoming",
            ),
            InlineKeyboardButton(
                f"支出提醒 {get_status_emoji(monitor_entry.notify_on_outgoing)}",
                callback_data=f"toggle:{address}:notify_on_outgoing",
            ),
        ],
        [
            InlineKeyboardButton(
                f"TRX 提醒 {get_status_emoji(monitor_entry.notify_trx)}",
                callback_data=f"toggle:{address}:notify_trx",
            ),
            InlineKeyboardButton(
                f"USDT 提醒 {get_status_emoji(monitor_entry.notify_usdt)}",
                callback_data=f"toggle:{address}:notify_usdt",
            ),
        ],
        [InlineKeyboardButton("📝 设置备注", callback_data=f"set_nickname:{address}")],
        [InlineKeyboardButton("<< 返回钱包列表", callback_data="show_monitoring_list")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_monitor_this_address_keyboard(address: str) -> InlineKeyboardMarkup:
    """
    创建一个包含“监听该地址”按钮的内联键盘。
    """
    keyboard = [
        [InlineKeyboardButton("监听该地址", callback_data=f"monitor_this:{address}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_smart_trx_packages_keyboard() -> InlineKeyboardMarkup:
    """
    构建“智能笔数”的套餐选择内联键盘。
    """
    keyboard = keyboard = [
        [
            InlineKeyboardButton("10笔", callback_data="smart_trx_size:10"),
            InlineKeyboardButton("20笔", callback_data="smart_trx_size:20"),
            InlineKeyboardButton("50笔", callback_data="smart_trx_size:50"),
        ],
        [
            InlineKeyboardButton("100笔", callback_data="smart_trx_size:100"),
            InlineKeyboardButton("200笔", callback_data="smart_trx_size:200"),
            InlineKeyboardButton("500笔", callback_data="smart_trx_size:500"),
        ],
        [
            InlineKeyboardButton("1000笔", callback_data="smart_trx_size:1000"),
            InlineKeyboardButton("2000笔", callback_data="smart_trx_size:2000"),
        ],
        # TODO
        # [
        #     InlineKeyboardButton("地址列表", callback_data="show_monitoring_list"),
        # ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_smart_trx_order_keyboard(order_id: str, current_currency: str) -> InlineKeyboardMarkup:
    """
    构建智能笔数订单的确认键盘。
    """
    # 根据当前币种决定切换按钮的文本
    switch_currency_text = "切换USDT支付" if current_currency == "TRX" else "切换TRX支付"
    switch_currency_callback = f"switch_currency:{order_id}:{ 'USDT' if current_currency == 'TRX' else 'TRX' }"

    keyboard = [
        [
            InlineKeyboardButton(switch_currency_text, callback_data=switch_currency_callback),
            InlineKeyboardButton("取消订单", callback_data=f"cancel_order:{order_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_customer_service_keyboard() -> InlineKeyboardMarkup:
    """
    创建一个包含"联系客服"链接按钮的内联键盘。
    """
    # 从 settings 中读取客服链接，如果不存在则使用默认值
    customer_service_url = getattr(settings, 'CUSTOMER_SERVICE_URL', 'https://t.me/happySea0001')
    
    # 确保 URL 是有效的格式
    if not customer_service_url or not (customer_service_url.startswith('http://') or customer_service_url.startswith('https://') or customer_service_url.startswith('tg://')):
        customer_service_url = 'https://t.me/happySea0001'  # 使用默认值
    
    keyboard = [
        [
            # URL 按钮使用 url 参数，而不是 callback_data
            InlineKeyboardButton("📞 联系客服", url=customer_service_url)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
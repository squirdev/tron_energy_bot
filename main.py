import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

# 核心应用模块的导入
from app.core.config import settings
from app.db.database import init_db

# 服务层导入
from app.services.monitoring_service import MonitoringService

# 处理器 (handlers) 导入
from app.bot.handlers import (
    start_command,
    handle_monitor_list,
    # 监听功能的回调处理器
    show_monitoring_list_callback,
    show_monitor_actions_callback,
    show_monitor_settings_callback,
    toggle_monitor_setting_callback,
    delete_monitor_address_callback,
    monitor_this_address_callback,
    # 会话处理器
    monitor_conv_handler,
    
)
# 主菜单按钮处理器
from app.bot.handlers_menu import (
    handle_energy_rent,
    handle_trx_exchange,
    handle_standard_energy,
    handle_special_offer
)
from app.bot.handlers_wallet_query import (
    handle_wallet_query, # 这是会话的入口
    wallet_query_conv_handler,
)
from app.bot.handlers_smart_trx import (
    handle_smart_trx,
    smart_trx_conv_handler,
    switch_currency_callback,
    cancel_order_callback
)
from app.bot import constants as const

from app.bot.payment_worker import payment_polling_worker
from app.bot.address_listener_worker import address_listener_worker
from app.services.balance_monitor_service import balance_monitor_worker

# --- 日志配置 ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.INFO) # 可以看到 websocket 连接信息
logger = logging.getLogger(__name__)

# 全局变量来持有 PTB Application 实例
ptb_app: Application | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用启动和关闭时执行的生命周期管理器
    """
    global ptb_app
    logger.info("--- Application starting up ---")
    
    # 1. 初始化数据库
    await init_db()

    # 2. 初始化 Telegram Bot Application
    ptb_app = Application.builder().token(settings.TELEGRAM_TOKEN).build()
    
    # 3. 将 ptb_app 实例传递给需要它的服务层，以便发送消息
    MonitoringService.ptb_app = ptb_app
    

    # --- 注册所有 Telegram 处理器 ---

    # 组 0 (最高优先级): 所有会话处理器。
    # 当一个会话激活时，它会优先处理消息。
    ptb_app.add_handler(monitor_conv_handler, group=0)
    ptb_app.add_handler(smart_trx_conv_handler, group=0)
    ptb_app.add_handler(wallet_query_conv_handler, group=0)
    
    # 组 1: 所有主菜单按钮的 MessageHandler。
    # 只有在没有活跃会话处理消息时，这些处理器才会被触发。
    # 它们中的一些会作为会话的入口点。
    button_handlers = [
        MessageHandler(filters.Text([const.BTN_SPECIAL_OFFER]), handle_special_offer),
        MessageHandler(filters.Text([const.BTN_MONITOR_LIST]), handle_monitor_list),
        MessageHandler(filters.Text([const.BTN_ENERGY_RENT]), handle_energy_rent),
        MessageHandler(filters.Text([const.BTN_TRX_EXCHANGE]), handle_trx_exchange),
        MessageHandler(filters.Text([const.BTN_TRUE_TRX]), handle_standard_energy),
        MessageHandler(filters.Text([const.BTN_SMART_TRX]), handle_smart_trx),
    ]
    ptb_app.add_handlers(handlers={1: button_handlers})
    
    # 组 2: 所有独立的内联键盘回调处理器。
    callback_handlers = [
        CallbackQueryHandler(switch_currency_callback, pattern='^switch_currency:'),
        CallbackQueryHandler(cancel_order_callback, pattern='^cancel_order:'),
        CallbackQueryHandler(monitor_this_address_callback, pattern='^monitor_this:'),
        CallbackQueryHandler(show_monitoring_list_callback, pattern='^show_monitoring_list$'),
        CallbackQueryHandler(show_monitor_actions_callback, pattern='^monitor_actions:'),
        CallbackQueryHandler(show_monitor_settings_callback, pattern='^monitor_settings:'),
        CallbackQueryHandler(toggle_monitor_setting_callback, pattern='^toggle:'),
        CallbackQueryHandler(delete_monitor_address_callback, pattern='^delete_monitor:'),
    ]
    if callback_handlers:
        ptb_app.add_handlers(handlers={2: callback_handlers})
    
    # 最后的 CommandHandler，确保 start 命令总是可用
    ptb_app.add_handler(CommandHandler("start", start_command), group=3)
   
    # 4. 初始化 PTB Application
    await ptb_app.initialize()

    # 5. 启动与 Telegram 的通信 (轮询模式)
    # 这段代码负责接收用户的消息和命令，必须保留
    logger.info("Starting bot in Polling mode...")
    await ptb_app.updater.start_polling(drop_pending_updates=True) # drop_pending_updates 可以在重启时忽略旧消息
    # start() 会启动所有组件，包括 JobQueue 的调度器
    await ptb_app.start()
    logger.info("Bot polling has started.")
    # --- 启动两个独立的后台任务 ---
    # 任务1：监听支付地址，用于确认订单
    asyncio.create_task(payment_polling_worker(ptb_app))
    # 任务2：监听用户添加的地址，用于收入支出提醒
    asyncio.create_task(address_listener_worker(ptb_app))
    # 任务3：监控 kuaizu.io 余额，余额不足时通知管理员
    asyncio.create_task(balance_monitor_worker(ptb_app))
    

    yield

    # --- 应用关闭时执行 ---
    logger.info("--- Application shutting down ---")
    if ptb_app:
        if ptb_app.updater and ptb_app.updater.is_running:
            logger.info("Stopping bot polling...")
            await ptb_app.updater.stop()
        if ptb_app.running:
             await ptb_app.stop()
        await ptb_app.shutdown()
        logger.info("Bot has been shut down.")

# --- FastAPI 应用实例 ---
app = FastAPI(lifespan=lifespan)

# --- API 根路由 ---
@app.get("/")
def read_root():
    return {"status": "ok", "bot_mode": "polling", "chain_monitor": "websocket"}
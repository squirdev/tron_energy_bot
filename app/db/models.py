import uuid
from datetime import datetime, timedelta
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field
from enum import Enum
from pymongo import IndexModel, ASCENDING


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "待支付"
    PAID = "已支付"
    COMPLETED = "已完成"
    EXPIRED = "已过期"
    CANCELED = "已取消"


class User(Document):
    user_id: Indexed(int, unique=True)
    chat_id: int
    username: Optional[str] = None
    tron_address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"

class OrderType(str, Enum):
    SPECIAL_OFFER = "特价能量"
    SMART_TRX = "智能笔数"

class Order(Document):
    """
    一个更通用的订单模型，适用于多种支付场景。
    """
    order_id: Indexed(str, unique=True) = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # --- 用户信息：不再直接关联整个 User 文档，而是存储关键 ID ---
    # 直接关联 (Beanie 称之为 Link) 会增加复杂性，对于简单场景存储 ID 更高效
    user_id: int
    chat_id: int

    # --- 订单核心信息 ---
    order_type: OrderType
    # 我们仍然希望 status 字段有索引，但会在下面的 Settings.indexes 中定义
    status: OrderStatus = Field(default=OrderStatus.PENDING_PAYMENT)
    
    # --- 支付信息 (这是最重要的部分) ---
    currency: str  # "TRX" 或 "USDT"
    expected_amount: float # 期望用户支付的、带有随机尾数的精确金额
    paid_amount: Optional[float] = None
    payment_txid: Optional[str] = None

    # --- 业务特定信息 (使用一个灵活的字典) ---
    # 不再需要 energy_amount, duration_days 等固定字段
    details: dict = Field(default_factory=dict)
    # 例如: 对于智能笔数, details = {"receiver_address": "T...", "size": 10}
    #       对于特价能量, details = {}

    # --- 时间戳 ---
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime # 订单创建时必须指定过期时间
    paid_at: Optional[datetime] = None

    def set_expiration(self):
        self.expires_at = datetime.utcnow() + timedelta(days=self.duration_days)

    class Settings:
        name = "orders"

class MonitorAddress(Document):
    """
    存储用户要监听的TRON地址及相关设置的模型
    """
    user_id: int  # 不再需要 Indexed()，因为我们在下面定义了复合索引
    address: str  # 同上

    nickname: str = Field(default="未设置备注") # 地址别名，方便用户识别

    # 通知设置
    notify_on_incoming: bool = Field(default=True) # 收入提醒
    notify_on_outgoing: bool = Field(default=True) # 支出提醒
    notify_trx: bool = Field(default=True)         # TRX 变动提醒
    notify_usdt: bool = Field(default=True)        # USDT 变动提醒
    subscription_id: Optional[str] = None # 存储 Crypto APIs 返回的订阅 ID

    created_at: datetime = Field(default_factory=datetime.utcnow)
    # 存储最后一次检查到的交易的时间戳 (毫秒级)
    # 默认为None，表示从未检查过
    last_checked_tx_timestamp: Optional[int] = None

    # TODO
    # class Settings:
    #     name = "orders"
    #     # 2. 使用 IndexModel 来正确定义索引
    #     # 为待支付订单和过期时间创建索引，加快轮询查询速度
    #     indexes = [
    #         # 为 status 字段创建一个普通索引，以加快按状态查询的速度
    #         IndexModel([("status", ASCENDING)]),
            
    #         # 保留我们之前为支付轮询创建的高效复合索引
    #         IndexModel([("status", ASCENDING), ("expires_at", ASCENDING)]),
    #     ]

class StreamState(Document):
    """
    用于为每个地址存储轮询任务的处理状态。
    """
    address: Indexed(str, unique=True) # 被监听的 TRON 地址
    last_processed_timestamp: int # 存储我们为这个地址处理过的最新交易的毫秒级时间戳

    class Settings:
        name = "stream_state"
        indexes = []

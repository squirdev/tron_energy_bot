import motor.motor_asyncio
from beanie import init_beanie
from app.core.config import settings
from app.db.models import User, Order, MonitorAddress,StreamState

async def init_db():
    """
    初始化数据库连接和Beanie ODM
    """
    client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URI)
    await init_beanie(
        database=client.get_default_database(), 
        document_models=[User, Order, MonitorAddress,StreamState]
    )
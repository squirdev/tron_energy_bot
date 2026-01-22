from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    # 加载 .env 文件
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TELEGRAM_TOKEN: str
    SPECIAL_OFFER_ADDRESS: str
    SPECIAL_OFFER_PRICE: float
    TRX_EXCHANGE_ADDRESS: str
    TRX_EXCHANGE_PRICE: float
    ENERGY_FLASH_ADDRESS: str
    ENERGY_FLASH_PRICE: float
    ENERGY_STANDARD_ADDRESS: str
    ENERGY_STANDARD_PRICE: float
    ENERGY_SMART_ADDRESS: str
    ENERGY_SMART_PRICE: float
    ENERGY_SMART_PRICE_USDT: float
    TRONGRID_API_KEY: str
    # Network configuration: "mainnet" or "testnet"
    TRON_NETWORK: str = "mainnet"
    # Testnet endpoint (only used if TRON_NETWORK=testnet)
    TRON_TESTNET_ENDPOINT: str | None = None
    KUAZU_API_KEY: str
    KUAZU_BALANCE_THRESHOLD: float = 20.0  # 余额告警阈值
    MONGO_URI: str
    ADMIN_CHAT_ID: int
    WEBHOOK_URL: str | None = None # Webhook可选
    CUSTOMER_SERVICE_URL: str

    @field_validator('KUAZU_BALANCE_THRESHOLD', mode='before')
    @classmethod
    def convert_balance_threshold(cls, v):
        if isinstance(v, str):
            return float(v)
        return v

# 创建一个全局可用的配置实例
settings = Settings()
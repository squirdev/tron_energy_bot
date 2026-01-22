import logging
from datetime import datetime
from pydantic import BaseModel
import asyncio
import httpx
import requests  # For synchronous USDT balance query
from typing import Optional, List 
# --- 导入 Tronpy ---
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.exceptions import AddressNotFound

from app.core.config import settings

# --- Pydantic 模型来规范化交易数据 ---
class TransactionData(BaseModel):
    tx_id: str
    from_address: str
    to_address: str
    token_symbol: str
    amount: float
    timestamp: int # 毫秒级时间戳


# --- Pydantic 模型 ---
class TronAccountDetails(BaseModel):
    address: str
    trx_balance: float = 0.0
    usdt_balance: float = 0.0
    energy_limit: int = 0
    energy_used: int = 0
    net_limit: int = 5000  # 免费带宽
    net_used: int = 0
    staked_bandwidth_limit: int = 0 # 质押带宽
    staked_bandwidth_used: int = 0
    total_staked: float = 0.0  # 质押资产 (TRX)
    creation_time: datetime
    last_operation_time: datetime

class TronService:
    """
    使用 tronpy 封装所有与 Tron 链交互的逻辑。
    支持主网和测试网。
    """
    # 在类级别初始化客户端，以便在所有方法中复用
    # 为了更好的性能和稳定性，建议使用付费的 TronGrid API Key
    # 如果您暂时没有 API Key，可以使用公共节点，但不稳定
    
    # 根据配置选择主网或测试网
    _is_testnet = settings.TRON_NETWORK.lower() == "testnet"
    
    if _is_testnet:
        # 测试网配置 (Shasta Testnet)
        testnet_url = settings.TRON_TESTNET_ENDPOINT or "https://api.shasta.trongrid.io"
        provider = HTTPProvider(testnet_url, api_key=settings.TRONGRID_API_KEY)
        client = Tron(network="shasta", provider=provider, conf={"fee_limit": 0})
        USDT_CONTRACT_ADDRESS = "TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs"  # Shasta testnet USDT
        logging.info(f"TronService initialized for TESTNET (Shasta) - Endpoint: {testnet_url}")
    else:
        # 主网配置 (Mainnet)
        provider = HTTPProvider(api_key=settings.TRONGRID_API_KEY)
        client = Tron(provider=provider, conf={"fee_limit": 0})
        USDT_CONTRACT_ADDRESS = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # Mainnet USDT
        logging.info("TronService initialized for MAINNET")
    
    USDT_DECIMALS = 6 # USDT 的小数位数

    CRYPTO_APIS_BASE_URL = "https://rest.cryptoapis.io"

    @staticmethod
    async def get_account_details(address: str) -> TronAccountDetails | None:
        """
        异步获取账户详情。
        通过在线程池中运行同步的 tronpy 调用来避免阻塞事件循环。
        """
        
        def _sync_fetch_details():
            """这个内部函数包含了所有同步的 tronpy 调用。"""
            # 1. 获取账户基本信息 (TRX余额, 创建/活跃时间, 质押等)
            try:
                account_info = TronService.client.get_account(address)
            except Exception as e:
                logging.error(f"Failed to get account info for {address}: {e}")
                raise

            # 2. 获取账户资源信息 (能量和带宽)
            try:
                resources = TronService.client.get_account_resource(address)
            except Exception as e:
                logging.warning(f"Failed to get account resources for {address}: {e}, using defaults")
                resources = {
                    "EnergyLimit": 0,
                    "EnergyUsed": 0,
                    "freeNetLimit": 5000,
                    "freeNetUsed": 0,
                    "NetLimit": 0,
                    "NetUsed": 0
                }

            # 3. 获取USDT余额 - 使用 requests 库（同步）而不是 tronpy 合约调用（避免 ABI 问题）
            try:
                # 使用 TronGrid API 直接查询 TRC20 余额，避免需要 ABI
                # Use correct endpoint based on network mode
                if TronService._is_testnet:
                    base_url = "https://api.shasta.trongrid.io"
                else:
                    base_url = "https://api.trongrid.io"
                trc20_url = f"{base_url}/v1/accounts/{address}/tokens"
                headers = {"TRON-PRO-API-KEY": settings.TRONGRID_API_KEY} if settings.TRONGRID_API_KEY else {}
                params = {"contract_address": TronService.USDT_CONTRACT_ADDRESS}
                
                response = requests.get(trc20_url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # 查找 USDT token
                usdt_balance = 0.0
                if "data" in data and len(data["data"]) > 0:
                    for token in data["data"]:
                        if token.get("token_address", "").upper() == TronService.USDT_CONTRACT_ADDRESS.upper():
                            usdt_balance = float(token.get("balance", 0)) / (10**TronService.USDT_DECIMALS)
                            break
            except Exception as e:
                logging.warning(f"Failed to get USDT balance for {address}: {e}, using 0")
                usdt_balance = 0.0

            # 4. 汇总质押信息 (能量和带宽)
            total_staked = 0
            if "frozen" in account_info:
                for item in account_info["frozen"]:
                    total_staked += item['frozen_balance']
            if "account_resource" in account_info and "frozen_balance_for_energy" in account_info["account_resource"]:
                 total_staked += account_info["account_resource"]["frozen_balance_for_energy"]["frozen_balance"]
            
            # 5. 组合所有数据并返回
            return {
                "address": address,
                "trx_balance": account_info.get("balance", 0) / 1_000_000, # TRX余额单位是sun
                "usdt_balance": usdt_balance,
                "energy_limit": resources.get("EnergyLimit", 0),
                "energy_used": resources.get("EnergyUsed", 0),
                "net_limit": resources.get("freeNetLimit", 0) + resources.get("NetLimit", 0),
                "net_used": resources.get("freeNetUsed", 0) + resources.get("NetUsed", 0),
                "staked_bandwidth_limit": resources.get("NetLimit", 0),
                "staked_bandwidth_used": resources.get("NetUsed", 0),
                "total_staked": total_staked / 1_000_000, # 质押资产单位是sun
                # 时间戳单位是毫秒，需要转换为秒
                "creation_time": datetime.fromtimestamp(account_info["create_time"] / 1000),
                "last_operation_time": datetime.fromtimestamp(account_info.get("latest_opration_time", account_info["create_time"]) / 1000)
            }

        try:
            # 获取当前的 asyncio 事件循环
            loop = asyncio.get_running_loop()
            
            # --- 关键步骤 ---
            # 在默认的线程池执行器中运行同步函数 _sync_fetch_details
            # 这会防止它阻塞 FastAPI 和 Telegram Bot 的主事件循环
            details_dict = await loop.run_in_executor(None, _sync_fetch_details)
            
            # 使用验证过的字典创建 Pydantic 模型实例
            return TronAccountDetails(**details_dict)
            
        except AddressNotFound:
            logging.warning(f"Address not found on Tron network: {address}")
            return None
        except Exception as e:
            logging.error(f"Error fetching account details for {address} using tronpy: {e}")
            return None

    @staticmethod
    async def get_new_transactions(address: str, since_timestamp: int) -> List[TransactionData]:
        """
        [重构] 使用 TronGrid 的免费 V1 API 获取一个地址在指定时间戳之后的新交易。
        支持主网和测试网。
        """
        all_new_transactions = []
        # 根据网络模式选择正确的 API 端点
        if TronService._is_testnet:
            base_url = "https://api.shasta.trongrid.io/v1/accounts"
            network_name = "Shasta Testnet"
        else:
            base_url = "https://api.trongrid.io/v1/accounts"
            network_name = "Mainnet"
        headers = {"TRON-PRO-API-KEY": settings.TRONGRID_API_KEY} # 假设 API Key 存储在 settings 中
        
        logging.debug(f"查询 {network_name} 交易: 地址={address[:10]}..., 时间戳>={since_timestamp}")
        
        # 为了避免错过交易，我们给时间戳一个小的缓冲
        # "only_confirmed": True 移除 only_confirmed 意味着您可能会获取到一些最终因为分叉等原因未被区块链接受的交易。虽然在 TRON 上这种情况非常罕见，但理论上存在。
        params = {"limit": 20, "min_timestamp": since_timestamp}

        async with httpx.AsyncClient(timeout=15) as client:
            # --- 1. 获取 TRC20 (USDT) 交易 ---
            try:
                # 只查询 USDT 合约
                trc20_url = f"{base_url}/{address}/transactions/trc20?contract_address={TronService.USDT_CONTRACT_ADDRESS}"
                resp = await client.get(trc20_url, headers=headers, params=params)
                resp.raise_for_status()
                
                for tx in resp.json().get("data", []):
                    all_new_transactions.append(TransactionData(
                        tx_id=tx['transaction_id'],
                        from_address=tx['from'],
                        to_address=tx['to'],
                        token_symbol='USDT',
                        amount=int(tx['value']) / (10**TronService.USDT_DECIMALS),
                        timestamp=tx['block_timestamp']
                    ))
            except Exception as e:
                logging.warning(f"轮询 TRC20 交易失败 ({address[:6]}...): {e}")

            # --- 2. 获取 TRX 交易 ---
            try:
                trx_url = f"{base_url}/{address}/transactions"
                resp = await client.get(trx_url, headers=headers, params=params)
                resp.raise_for_status()

                for tx in resp.json().get("data", []):
                    contract_data = tx.get("raw_data", {}).get("contract", [{}])[0]
                    if contract_data.get("type") == "TransferContract":
                        value = contract_data.get("parameter", {}).get("value", {})
                        amount = value.get('amount', 0) / 1_000_000
                        if amount > 0:
                            all_new_transactions.append(TransactionData(
                                tx_id=tx['txID'],
                                from_address=TronService.client.to_base58check_address(value.get('owner_address')),
                                to_address=TronService.client.to_base58check_address(value.get('to_address')),
                                token_symbol='TRX',
                                amount=amount,
                                timestamp=tx['block_timestamp'] 
                            ))
            except Exception as e:
                logging.warning(f"轮询 TRX 交易失败 ({address[:6]}...): {e}")

        # 按时间戳排序并去重
        # (因为可能同时获取到TRX和TRC20的同一笔交易的不同视角)
        unique_transactions = {tx.tx_id: tx for tx in all_new_transactions}
        sorted_transactions = sorted(unique_transactions.values(), key=lambda t: t.timestamp)
        
        return sorted_transactions

    # 根据交易哈希获取付款方地址
    @staticmethod
    async def get_sender_from_txid(tx_id: str) -> Optional[str]:
        """
        根据交易哈希 (TxID) 查询并返回该交易的付款方地址。
        """
        def _sync_fetch():
            try:
                # 使用 tronpy 获取交易详情
                tx_info = TronService.client.get_transaction(tx_id)
                
                # 从 raw_data 中提取 owner_address (付款方)
                owner_address_hex = tx_info['raw_data']['contract'][0]['parameter']['value']['owner_address']
                
                # 将十六进制地址转换为 Base58 格式
                return TronService.client.to_base58check_address(owner_address_hex)
                
            except Exception as e:
                logging.error(f"根据 TxID {tx_id} 查询付款方地址失败: {e}")
                return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_fetch)        

    @staticmethod
    async def get_new_transactions333(address: str, since_timestamp: int) -> List[TransactionData]:
        """
        [调试版] 使用 TronGrid V1 API 获取新交易，并打印详细日志。
        """
        # --- 打印日志 1: 函数入口 ---
        logging.info(f"[get_new_transactions] 正在为地址 {address} 查询时间戳 > {since_timestamp} 的交易...")
        
        all_new_transactions = []
        # Use correct endpoint based on network mode
        if TronService._is_testnet:
            base_url = "https://api.shasta.trongrid.io/v1/accounts"
            network_name = "Shasta Testnet"
        else:
            base_url = "https://api.trongrid.io/v1/accounts"
            network_name = "Mainnet"
        headers = {"TRON-PRO-API-KEY": settings.TRONGRID_API_KEY}
        
        params = {"limit": 20, "min_timestamp": since_timestamp}

        async with httpx.AsyncClient(timeout=15) as client:
            # --- 1. 获取 TRC20 (USDT) 交易 ---
            try:
                trc20_url = f"{base_url}/{address}/transactions/trc20?contract_address={TronService.USDT_CONTRACT_ADDRESS}"
                resp = await client.get(trc20_url, headers=headers, params=params)
                
                # --- 打印日志 2: TRC20 API 的原始响应 ---
                logging.info(f"[get_new_transactions] TRC20 API Response for {address[:6]}: Status={resp.status_code}, Body={resp.text}")

                resp.raise_for_status()
                
                for tx in resp.json().get("data", []):
                    # (解析逻辑不变)
                    all_new_transactions.append(TransactionData(
                        tx_id=tx['transaction_id'],
                        from_address=tx['from'],
                        to_address=tx['to'],
                        token_symbol='USDT',
                        amount=int(tx['value']) / (10**TronService.USDT_DECIMALS),
                        timestamp=tx['block_timestamp']
                    ))
            except Exception as e:
                logging.warning(f"轮询 TRC20 交易失败 ({address[:6]}...): {e}")

            # --- 2. 获取 TRX 交易 ---
            try:
                trx_url = f"{base_url}/{address}/transactions"
                resp = await client.get(trx_url, headers=headers, params=params)

                # --- 打印日志 3: TRX API 的原始响应 ---
                logging.info(f"[get_new_transactions] TRX API Response for {address[:6]}: Status={resp.status_code}, Body={resp.text}")

                resp.raise_for_status()

                for tx in resp.json().get("data", []):
                    # (解析逻辑不变)
                    contract_data = tx.get("raw_data", {}).get("contract", [{}])[0]
                    if contract_data.get("type") == "TransferContract":
                        value = contract_data.get("parameter", {}).get("value", {})
                        amount = value.get('amount', 0) / 1_000_000
                        if amount > 0:
                            all_new_transactions.append(TransactionData(
                                tx_id=tx['txID'],
                                from_address=TronService.client.to_base58check_address(value.get('owner_address')),
                                to_address=TronService.client.to_base58check_address(value.get('to_address')),
                                token_symbol='TRX',
                                amount=amount,
                                timestamp=tx['raw_data']['timestamp']
                            ))
            except Exception as e:
                logging.warning(f"轮询 TRX 交易失败 ({address[:6]}...): {e}")

        # (去重和排序逻辑不变)
        unique_transactions = {tx.tx_id: tx for tx in all_new_transactions}
        sorted_transactions = sorted(unique_transactions.values(), key=lambda t: t.timestamp)
        
        # --- 打印日志 4: 函数出口 ---
        logging.info(f"[get_new_transactions] 本次查询共找到 {len(sorted_transactions)} 笔唯一的、符合条件的交易。")
        
        return sorted_transactions
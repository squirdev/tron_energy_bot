import logging
import json
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any

from app.services.monitoring_service import MonitoringService
from app.services.tron_service import TransactionData

router = APIRouter(
    prefix="/webhook",
    tags=["Webhook"]
)

@router.post("/cryptoapis")
async def handle_cryptoapis_webhook(request: Request):
    """
    接收并处理来自 Crypto APIs 的 Webhook 回调。
    此版本精确适配官方示例的返回数据结构。
    """
    try:
        payload = await request.json()
        logging.info("收到 Crypto APIs webhook 推送。")
        logging.debug(f"完整 Payload: {json.dumps(payload, indent=2)}")

        event_data = payload.get("data", {}).get("item", {})
        if not event_data:
            return {"status": "ignored", "reason": "no event data"}

        # --- 精确解析 Crypto APIs 的数据结构 ---
        
        token_info = event_data.get("token", {})
        token_symbol = token_info.get("symbol", "TRX").upper() # 如果没有 symbol, 假定为 TRX
        amount = float(token_info.get("amount", "0"))
        
        # 使用 direction 字段来确定 from 和 to
        direction = event_data.get("direction")
        monitored_address = event_data.get("address")
        
        # 我们需要找到交易的另一方。这需要通过 tronpy 再次查询交易详情获得。
        # 这是一个简化处理，在真实场景中，您需要根据 transactionId 查询交易详情
        # 才能可靠地获取 from 和 to。
        # 这里我们先做一个占位符。
        # from_address = "需要查询获得" if direction == "incoming" else monitored_address
        # to_address = monitored_address if direction == "incoming" else "需要查询获得"
        # 更好的方法是直接使用 `handle_webhook_transaction` 的逻辑
        from_address = ""
        to_address = ""

        # 为了避免再次查询，我们可以直接使用 MonitoringService 的逻辑
        # 它会自己判断 from 和 to
        if direction == "incoming":
            to_address = monitored_address
        else:
            from_address = monitored_address

        tx = TransactionData(
            tx_id=event_data.get("transactionId"),
            from_address=from_address, # 暂时留空，让 service 层处理
            to_address=to_address,   # 暂时留空，让 service 层处理
            token_symbol=token_symbol,
            amount=amount,
            # 时间戳在 minedInBlock 对象里
            timestamp=int(event_data.get("minedInBlock", {}).get("timestamp", 0)) * 1000
        )

        # 这里的 tx 对象还不完整，但包含了核心信息
        # 我们将它传递给 service 层，service 层需要被改造
        await MonitoringService.handle_cryptoapis_transaction(event_data)

        return {"referenceId": payload.get("referenceId")}

    except Exception as e:
        logging.error(f"处理 Crypto APIs webhook 时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
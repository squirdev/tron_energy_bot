import logging
import httpx
import asyncio

from app.db.models import Order, OrderType, OrderStatus
from app.core.config import settings
from app.services.tron_service import TronService

class EnergyService:
    """
    封装所有与能量租赁、发放相关的业务逻辑，特别是调用第三方 API。
    """
    KUAZU_API_URL = "https://api.kuaizu.io/api/rent"

    @staticmethod
    async def process_paid_order(order: Order, ptb_app):
        """
        根据已支付的订单类型，执行相应的能量发放逻辑。
        """
        logging.info(f"正在处理已支付的订单 {order.order_id}，类型为 {order.order_type.value}")

        success = False
        user_message = ""

        if order.order_type == OrderType.SPECIAL_OFFER:
            success, user_message = await EnergyService.delegate_special_offer_energy(order)
        elif order.order_type == OrderType.SMART_TRX:
            # 您可以在这里添加“智能笔数”订单支付成功后的逻辑
            # 例如：通知用户服务已激活
            success = True
            user_message = (f"您的 **{order.details.get('size', '')}笔** 智能笔数套餐已成功激活！\n"
                          f"能量将自动代理至地址: `{order.details.get('receiver_address')}`")

        # 无论成功与否，都更新订单状态
        order.status = OrderStatus.COMPLETED if success else order.status # 如果失败，可以保持 PAID 状态以便重试
        await order.save()
        logging.info(f"订单 {order.order_id} 处理完成，状态: {order.status.value}")
        
        # 如果有需要通知给用户的特定消息，则发送
        if user_message:
            try:
                await ptb_app.bot.send_message(chat_id=order.chat_id, text=user_message, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"发送订单处理结果通知失败: {e}")


    @staticmethod
    async def delegate_special_offer_energy(order: Order) -> (bool, str):
        """
        为"特价能量"订单调用 kuaizu.io API 发放能量。
        自动将能量租给支付该订单的地址。
        注意：在测试网模式下，kuaizu.io 不支持，将返回模拟成功消息。
        """
        # 如果是测试网，跳过 kuaizu.io API 调用（不支持测试网）
        if settings.TRON_NETWORK.lower() == "testnet":
            logging.warning(f"测试网模式：跳过 kuaizu.io API 调用（订单 {order.order_id}）")
            if not order.payment_txid:
                return False, "订单处理失败：无法确认付款交易。"
            receiver_address = await TronService.get_sender_from_txid(order.payment_txid)
            if not receiver_address:
                return False, "订单处理失败：无法解析付款方地址。"
            # 返回模拟成功消息（测试网模式）
            success_message = (
                f"🎉 [测试网模式] 能量已模拟到账！\n\n"
                f"**接收地址:** `{receiver_address}`\n"
                f"**租赁数量:** 65,000 能量（模拟）\n"
                f"**注意:** 这是测试网模式，kuaizu.io 不支持测试网，能量未实际发放。"
            )
            return True, success_message
        
        # --- 关键修改：不再从 details 获取，而是通过 txid 查询 ---
        if not order.payment_txid:
            logging.error(f"特价能量订单 {order.order_id} 缺少 payment_txid！")
            return False, "订单处理失败：无法确认付款交易。"

        logging.info(f"正在根据 TxID {order.payment_txid} 查询付款方地址...")
        receiver_address = await TronService.get_sender_from_txid(order.payment_txid)

        if not receiver_address:
            logging.error(f"无法从 TxID {order.payment_txid} 中解析出付款方地址！")
            return False, "订单处理失败：无法解析付款方地址。"
        
        logging.info(f"查询到付款方地址 (即能量接收地址) 为: {receiver_address}")

        # --- 后续调用 kuaizu.io API ---
        payload = {
            "apiKey": settings.KUAZU_API_KEY,
            "resType": "ENERGY",
            "payNums": 65000,
            "rentTime": 15,
            "receiveAddress": receiver_address # <-- 使用我们查询到的地址
        }

        logging.info(f"正在为订单 {order.order_id} 调用 kuaizu.io API: {payload}")
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(EnergyService.KUAZU_API_URL, json=payload)
                response.raise_for_status()
                result = response.json()
            
            if result.get("code") == 1:
                logging.info(f"kuaizu.io API 调用成功！响应: {result}")
                order.details["delegate_txid"] = result.get("data", {}).get("hash")
                success_message = (f"🎉 能量已成功到账！\n\n"
                                 f"**接收地址:** `{receiver_address}`\n"
                                 f"**租赁数量:** 65,000 能量\n"
                                 f"**交易 HASH:** `{order.details['delegate_txid']}`")
                return True, success_message
            else:
                logging.error(f"kuaizu.io API 返回错误。Code: {result.get('code')}, Msg: {result.get('msg')}")
                error_message = f"能量租赁失败: {result.get('msg', '未知错误')}"
                return False, error_message

        except httpx.HTTPStatusError as e:
            logging.error(f"调用 kuaizu.io API 时发生 HTTP 错误: {e.response.status_code} - {e.response.text}")
            return False, "能量租赁服务暂时不可用，请联系客服。"
        except Exception as e:
            logging.error(f"调用 kuaizu.io API 时发生未知错误: {e}", exc_info=True)
            return False, "能量租赁服务出现未知错误，请联系客服。"
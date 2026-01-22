# Testnet Setup Guide & Dynamic TRX Price

This guide answers your questions about:
1. How to handle changing TRX prices (make it dynamic)
2. Using Test TRX (testnet) instead of real TRX
3. Using testnet wallet addresses

---

## Question 1: TRX Price Always Changes - How to Set It?

### Current Situation:
The code currently uses a **static price** from `.env` file:
```python
# In handlers_menu.py line 164:
rate = settings.TRX_EXCHANGE_PRICE  # Static value from .env
```

### Solution: Make It Dynamic

You have **two options**:

#### **Option A: Manual Update (Simple but requires manual work)**
- Set a reasonable price in `.env` (e.g., `TRX_EXCHANGE_PRICE=10.0`)
- Update it manually when market price changes significantly
- **Pros**: Simple, no code changes
- **Cons**: Requires manual updates, price can be outdated

#### **Option B: Dynamic Price Fetching (Recommended)**
Fetch real-time TRX price from an API. See the code modification below.

---

## Question 2: Can I Use Test TRX (Testnet)?

**YES! Absolutely!** You can use TRON testnet for testing. Here's how:

### Step 1: Get Testnet Wallet Addresses

1. **Install a TRON wallet** that supports testnet:
   - **TronLink** (browser extension): Switch to "Shasta Testnet"
   - **Trust Wallet**: Can create testnet wallets
   - Or use any TRON wallet that supports testnet

2. **Create a testnet wallet** and copy the address (starts with `T`)

3. **Get free test TRX**:
   - Visit: https://www.trongrid.io/faucet
   - Or: https://nileex.io/join/getJoinPage
   - Enter your testnet address
   - Receive free test TRX (not real money!)

### Step 2: Configure Code for Testnet

The current code uses **mainnet** by default. You need to modify it for testnet.

**Testnet endpoints:**
- Shasta Testnet: `https://api.shasta.trongrid.io`
- Nile Testnet: `https://api.nileex.io`

**Testnet USDT contract address:**
- Shasta: `TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf` (test USDT)
- Nile: Different test USDT address

---

## Question 3: I Already Set Testnet Addresses - Is It Possible?

**Yes, but you need to configure the code to use testnet endpoints!**

Currently, the code connects to **mainnet** by default. If you use testnet addresses with mainnet endpoints, transactions won't work.

---

## Implementation: Making It Work with Testnet

### Step 1: Add Testnet Configuration to `.env`

Add these new variables to your `.env`:

```env
# Network Configuration
TRON_NETWORK=testnet  # Options: "mainnet" or "testnet"
TRON_TESTNET_ENDPOINT=https://api.shasta.trongrid.io  # For testnet

# If using mainnet, leave TRON_TESTNET_ENDPOINT empty or use mainnet endpoint
```

### Step 2: Modify `app/core/config.py`

Add testnet configuration:

```python
TRON_NETWORK: str = "mainnet"  # or "testnet"
TRON_TESTNET_ENDPOINT: str | None = None
```

### Step 3: Modify `app/services/tron_service.py`

Update the TronService to support testnet:

```python
# At the top of TronService class:
if settings.TRON_NETWORK == "testnet":
    # Use testnet endpoint
    testnet_url = settings.TRON_TESTNET_ENDPOINT or "https://api.shasta.trongrid.io"
    provider = HTTPProvider(testnet_url, api_key=settings.TRONGRID_API_KEY)
    client = Tron(network="shasta", provider=provider, conf={"fee_limit": 0})
    USDT_CONTRACT_ADDRESS = "TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf"  # Testnet USDT
else:
    # Use mainnet (current code)
    provider = HTTPProvider(api_key=settings.TRONGRID_API_KEY)
    client = Tron(provider=provider, conf={"fee_limit": 0})
    USDT_CONTRACT_ADDRESS = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # Mainnet USDT
```

---

## Implementation: Dynamic TRX Price

### Option 1: Simple API Fetch (Recommended)

Create a new service to fetch TRX price:

**File: `app/services/price_service.py`** (new file)

```python
import httpx
import logging
from typing import Optional

class PriceService:
    """Service to fetch real-time cryptocurrency prices"""
    
    # Free API endpoints (no API key needed)
    COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price"
    BINANCE_API = "https://api.binance.com/api/v3/ticker/price"
    
    @staticmethod
    async def get_trx_price_usd() -> Optional[float]:
        """
        Fetch current TRX price in USD from CoinGecko (free, no API key needed)
        Returns: TRX price in USD, or None if fetch fails
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # CoinGecko: Get TRX price in USD
                response = await client.get(
                    PriceService.COINGECKO_API,
                    params={"ids": "tron", "vs_currencies": "usd"}
                )
                response.raise_for_status()
                data = response.json()
                price = data.get("tron", {}).get("usd")
                if price:
                    logging.info(f"Fetched TRX price: ${price:.4f} USD")
                    return float(price)
        except Exception as e:
            logging.error(f"Failed to fetch TRX price: {e}")
        
        return None
    
    @staticmethod
    async def get_usdt_to_trx_rate() -> Optional[float]:
        """
        Calculate how many TRX per 1 USDT
        Returns: TRX per USDT (e.g., 10.0 means 1 USDT = 10 TRX)
        """
        trx_price = await PriceService.get_trx_price_usd()
        if trx_price and trx_price > 0:
            # 1 USDT = 1 USD (approximately)
            # So: 1 USDT = 1 / TRX_price_in_USD
            rate = 1.0 / trx_price
            return rate
        return None
```

### Option 2: Update `handlers_menu.py` to Use Dynamic Price

Modify the `handle_trx_exchange` function:

```python
from app.services.price_service import PriceService

async def handle_trx_exchange(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """处理 "TRX兑换" 按钮"""
    clear_pending_actions(context)
    exchange_address = settings.TRX_EXCHANGE_ADDRESS
    
    # Try to fetch dynamic price, fallback to static if fails
    rate = await PriceService.get_usdt_to_trx_rate()
    if rate is None:
        # Fallback to static price from .env
        rate = settings.TRX_EXCHANGE_PRICE
        logging.warning("Using static TRX price from .env (dynamic fetch failed)")
    
    rate_for_100_usdt = f"{100 * rate:.2f}"
    
    response_text = textwrap.dedent(
        f"""
        💹实时汇率: 100 USDT = {rate_for_100_usdt} TRX
        {'(实时价格)' if rate != settings.TRX_EXCHANGE_PRICE else '(静态价格)'}

        往🔻下方地址转USDT,会5秒内自动回你TRX
        <code>{exchange_address}</code>
        (点击地址自动复制)
        ...
        """
    )
    # ... rest of the code
```

---

## Quick Setup Summary

### For Testnet Testing:

1. **Add to `.env`:**
   ```env
   TRON_NETWORK=testnet
   TRON_TESTNET_ENDPOINT=https://api.shasta.trongrid.io
   ```

2. **Use testnet wallet addresses** (you already have these)

3. **Get free test TRX** from faucet

4. **Modify code** to support testnet (see code above)

### For Dynamic TRX Price:

1. **Create `app/services/price_service.py`** (see code above)

2. **Update `handlers_menu.py`** to use dynamic price

3. **Keep `TRX_EXCHANGE_PRICE` in `.env` as fallback** (in case API fails)

---

## Important Notes

⚠️ **Testnet vs Mainnet:**
- **Testnet**: Free test coins, for development/testing only
- **Mainnet**: Real TRX, real money, for production
- **You cannot mix them!** Testnet addresses won't work on mainnet and vice versa

⚠️ **Price API Rate Limits:**
- CoinGecko free tier: ~50 calls/minute
- If you exceed limits, the code will fallback to static price from `.env`

---

## Next Steps

1. **For testing**: Set up testnet configuration
2. **For production**: Use mainnet with dynamic price fetching
3. **Test thoroughly** on testnet before going to mainnet!

Would you like me to implement these code changes for you?


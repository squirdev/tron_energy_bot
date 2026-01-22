# Environment Variables Setup Guide

This guide will help you configure all environment variables step by step to make this project your own.

---

## Quick Start: Complete .env Template

Create a file named `.env` in the project root directory and copy this template:

```env
# ============================================
# Telegram Bot Configuration
# ============================================
TELEGRAM_TOKEN=your_telegram_bot_token_here
ADMIN_CHAT_ID=your_telegram_chat_id_here

# ============================================
# TRON Blockchain Configuration
# ============================================
TRONGRID_API_KEY=your_trongrid_api_key_here

# ============================================
# Business Wallet Addresses (TRON Addresses)
# ============================================
SPECIAL_OFFER_ADDRESS=TYourSpecialOfferAddressHere
ENERGY_FLASH_ADDRESS=TYourFlashRentAddressHere
ENERGY_STANDARD_ADDRESS=TYourStandardEnergyAddressHere
ENERGY_SMART_ADDRESS=TYourSmartTrxAddressHere
TRX_EXCHANGE_ADDRESS=TYourExchangeAddressHere

# ============================================
# Product Pricing (in TRX)
# ============================================
SPECIAL_OFFER_PRICE=1.5
ENERGY_FLASH_PRICE=0.5
ENERGY_STANDARD_PRICE=0.3
ENERGY_SMART_PRICE=0.2
ENERGY_SMART_PRICE_USDT=0.02
TRX_EXCHANGE_PRICE=10.0

# ============================================
# Kuaizu.io API Configuration
# ============================================
KUAZU_API_KEY=your_kuaizu_api_key_here
KUAZU_BALANCE_THRESHOLD=20.0

# ============================================
# Database Configuration
# ============================================
MONGO_URI=mongodb://localhost:27017/energybot

# ============================================
# Optional Configuration
# ============================================
# WEBHOOK_URL=
CUSTOMER_SERVICE_URL=https://t.me/your_support_username
```

**Now follow the steps below to fill in each value.**

---

## Step 1: Create Your .env File

1. Create a new file named `.env` in the project root directory (same folder as `main.py`)

2. Copy the template above into your `.env` file

3. Follow the steps below to fill in each value

---

## Step 2: Get Your Telegram Bot Token

### What it is:
A unique token that identifies your bot to Telegram's servers.

### How to get it:

1. **Open Telegram** (on your phone or desktop)
2. **Search for `@BotFather`** and start a conversation
3. **Send the command**: `/newbot`
4. **Follow the prompts**:
   - Choose a name for your bot (e.g., "My Energy Bot")
   - Choose a username (must end in `bot`, e.g., "my_energy_bot")
5. **BotFather will give you a token** that looks like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
6. **Copy this token** and paste it into `.env`:
   ```
   TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### ⚠️ Important:
- **Never share this token publicly** (don't commit it to Git)
- If someone gets your token, they can control your bot

---

## Step 3: Get Your Admin Chat ID

### What it is:
Your personal Telegram chat ID. The bot uses this to send you admin notifications (like low balance warnings).

### How to get it:

**Method 1: Using a helper bot (Easiest)**
1. Open Telegram and search for `@userinfobot`
2. Start a conversation with it
3. It will immediately reply with your chat ID (a number like `123456789`)
4. Copy this number

**Method 2: Using your bot's API**
1. After setting `TELEGRAM_TOKEN`, send a message to your bot
2. Visit this URL in your browser (replace `YOUR_TOKEN` with your actual token):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Look for a JSON response with `"chat":{"id":123456789}`
4. Copy that number

**Method 3: Using a simple Python script**
```python
import requests
TOKEN = "your_bot_token_here"
response = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates")
print(response.json())
```
Look for `"chat":{"id":...}` in the output.

### Add to .env:
```
ADMIN_CHAT_ID=123456789
```

---

## Step 4: Get TronGrid API Key

### What it is:
An API key from TronGrid that allows your bot to query TRON blockchain data (transactions, balances, etc.).

### How to get it:

1. **Visit**: https://www.trongrid.io/
2. **Sign up** for a free account (or log in if you have one)
3. **Go to Dashboard** → **API Keys** section
4. **Click "Create API Key"** or use an existing one
5. **Copy the API key** (it's a long string)
6. **Add to .env**:
   ```
   TRONGRID_API_KEY=your_trongrid_api_key_here
   ```

### ⚠️ Note:
- Free tier has rate limits (requests per second)
- For production, consider upgrading to a paid plan

---

## Step 5: Set Up Your TRON Wallet Addresses

### What they are:
TRON wallet addresses where users will send payments. These should be **addresses you control**.

### How to get/create them:

**Option A: Use an existing TRON wallet**
- If you already have a TRON wallet (TronLink, Trust Wallet, etc.), use those addresses
- Format: Starts with `T` followed by 33 characters (e.g., `TYourAddressHere1234567890`)

**Option B: Create new TRON addresses**
1. Install a TRON wallet app (TronLink, Trust Wallet, etc.)
2. Create a new wallet
3. Copy the address (starts with `T`)
4. **Save the private key/seed phrase securely!**

### For testing, you can use the same address for all products:

```
SPECIAL_OFFER_ADDRESS=TYourAddressHere1234567890
ENERGY_FLASH_ADDRESS=TYourAddressHere1234567890
ENERGY_STANDARD_ADDRESS=TYourAddressHere1234567890
ENERGY_SMART_ADDRESS=TYourAddressHere1234567890
TRX_EXCHANGE_ADDRESS=TYourAddressHere1234567890
```

### ⚠️ Important:
- **You must control these addresses** (have the private keys)
- Users will send TRX/USDT to these addresses
- Make sure you can access funds sent to these addresses

---

## Step 6: Set Product Prices

### What they are:
Prices (in TRX or USDT) for each product your bot sells.

### How to set them:

Set reasonable prices based on your costs and market rates. Examples:

```
# Special Offer Energy (base price, random suffix added automatically)
SPECIAL_OFFER_PRICE=1.5

# Energy Flash Rent (per unit, users can buy 1-5 units)
ENERGY_FLASH_PRICE=0.5

# Standard Energy (per transaction)
ENERGY_STANDARD_PRICE=0.3

# Smart TRX (in TRX)
ENERGY_SMART_PRICE=0.2

# Smart TRX (in USDT)
ENERGY_SMART_PRICE_USDT=0.02

# TRX Exchange rate (TRX per 1 USDT)
# Example: If 1 USDT = 10 TRX, then TRX_EXCHANGE_PRICE=10.0
TRX_EXCHANGE_PRICE=10.0
```

### 💡 Tips:
- Start with test prices (very low) to test the system
- Adjust based on market rates and your profit margins
- You can change these anytime by editing `.env` and restarting

---

## Step 7: Get Kuaizu.io API Key (Optional but Recommended)

### What it is:
Kuaizu.io is a third-party service that rents TRON energy. Your bot uses it to automatically delegate energy to users after they pay.

### How to get it:

1. **Visit**: https://kuaizu.io/ (or search for kuaizu.io)
2. **Sign up** for an account
3. **Go to API settings** or dashboard
4. **Generate/Copy your API key**
5. **Add to .env**:
   ```
   KUAZU_API_KEY=your_kuaizu_api_key_here
   ```

### ⚠️ Note:
- If you don't have a kuaizu.io account, you may need to:
  - Sign up and deposit funds
  - Or find an alternative energy rental service
  - Or modify the code to use a different service

### Balance Threshold:
```
KUAZU_BALANCE_THRESHOLD=20.0
```
This means: when your kuaizu.io balance drops below 20 TRX, you'll get a warning message.

---

## Step 8: Set Up MongoDB Database

### What it is:
MongoDB stores all your bot's data (orders, users, monitored addresses, etc.).

### Option A: Local MongoDB (For Testing)

1. **Install MongoDB**:
   - Windows: Download from https://www.mongodb.com/try/download/community
   - Mac: `brew install mongodb-community`
   - Linux: `sudo apt-get install mongodb`

2. **Start MongoDB**:
   - Windows: MongoDB should start as a service automatically
   - Mac/Linux: `mongod` (or `brew services start mongodb-community` on Mac)

3. **Use this connection string**:
   ```
   MONGO_URI=mongodb://localhost:27017/energybot
   ```

### Option B: MongoDB Atlas (Cloud - Recommended for Production)

1. **Visit**: https://www.mongodb.com/cloud/atlas
2. **Sign up** for a free account
3. **Create a new cluster** (free tier available)
4. **Create a database user**:
   - Go to "Database Access" → "Add New Database User"
   - Username: `energybot`
   - Password: (choose a strong password)
5. **Whitelist your IP**:
   - Go to "Network Access" → "Add IP Address"
   - For testing, you can allow all IPs: `0.0.0.0/0` (⚠️ less secure)
6. **Get connection string**:
   - Go to "Clusters" → "Connect" → "Connect your application"
   - Copy the connection string
   - Replace `<password>` with your database user password
   - Example:
     ```
     MONGO_URI=mongodb+srv://energybot:your_password@cluster0.xxxxx.mongodb.net/energybot?retryWrites=true&w=majority
     ```

---

## Step 9: Optional Settings

### Customer Service URL:
A link to your support channel/group. Users can click this for help.

```
CUSTOMER_SERVICE_URL=https://t.me/your_support_username
```

### Webhook URL (Leave Empty for Testing):
For production, you might use webhooks instead of polling. For now, leave it empty or commented out:

```
# WEBHOOK_URL=
```

---

## Step 10: Verify Your Configuration

### Quick Checklist:

- [ ] `TELEGRAM_TOKEN` - Your bot token from BotFather
- [ ] `ADMIN_CHAT_ID` - Your personal Telegram chat ID
- [ ] `TRONGRID_API_KEY` - Your TronGrid API key
- [ ] All `*_ADDRESS` variables - Your TRON wallet addresses
- [ ] All `*_PRICE` variables - Your product prices
- [ ] `KUAZU_API_KEY` - Your kuaizu.io API key (if using)
- [ ] `MONGO_URI` - Your MongoDB connection string
- [ ] `CUSTOMER_SERVICE_URL` - Your support link

---

## Step 11: Test Your Setup

1. **Make sure MongoDB is running** (if using local MongoDB)

2. **Start the bot**:
   ```bash
   uvicorn main:app --reload
   ```

3. **Check for errors**:
   - If you see "Application starting up" and "Bot polling has started", you're good!
   - If you see errors about missing variables, check your `.env` file

4. **Test your bot**:
   - Open Telegram
   - Search for your bot (by the username you gave it)
   - Send `/start`
   - You should see the main menu!

---

## Troubleshooting

### "Missing required environment variable"
- Make sure all required variables in `.env` are filled in
- Check for typos (no extra spaces, correct variable names)

### "MongoDB connection failed"
- Make sure MongoDB is running (if local)
- Check your `MONGO_URI` connection string
- If using Atlas, check your IP whitelist

### "Telegram bot token invalid"
- Double-check your `TELEGRAM_TOKEN`
- Make sure there are no extra spaces or quotes

### "TronGrid API rate limit exceeded"
- You're making too many requests
- Wait a bit, or upgrade your TronGrid plan

---

## Security Notes

1. **Never commit `.env` to Git**
   - Make sure `.env` is in your `.gitignore` file

2. **Keep your tokens secret**
   - Don't share your `.env` file
   - Don't paste tokens in public places

3. **Use strong passwords** for MongoDB and API accounts

---

## Next Steps

Once your bot is running:
1. Test each menu option
2. Try creating a test order
3. Monitor the logs for any issues
4. Adjust prices as needed

Good luck! 🚀


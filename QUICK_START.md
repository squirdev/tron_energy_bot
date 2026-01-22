# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Create `.env` file
Create a file named `.env` in the project root (same folder as `main.py`)

### 2. Copy the template from `SETUP_GUIDE.md`
Open `SETUP_GUIDE.md` and copy the complete `.env` template at the top.

### 3. Fill in the minimum required values:

#### ✅ Must Have (to start the bot):
- **TELEGRAM_TOKEN**: Get from @BotFather on Telegram
- **ADMIN_CHAT_ID**: Get from @userinfobot on Telegram  
- **TRONGRID_API_KEY**: Get from https://www.trongrid.io/
- **MONGO_URI**: Use `mongodb://localhost:27017/energybot` for local MongoDB
- **All *_ADDRESS**: Your TRON wallet addresses (can use same address for all)
- **All *_PRICE**: Set test prices (e.g., 0.1, 0.2, etc.)
- **KUAZU_API_KEY**: Get from https://kuaizu.io/ (if using energy rental)
- **CUSTOMER_SERVICE_URL**: Your Telegram support link

### 4. Start the bot:
```bash
uvicorn main:app --reload
```

### 5. Test:
- Open Telegram
- Find your bot
- Send `/start`

---

## 📖 For Detailed Instructions

See **`SETUP_GUIDE.md`** for step-by-step instructions on how to get each value.

---

## ⚠️ Important Notes

1. **Never commit `.env` to Git** (already in `.gitignore`)
2. **Keep your tokens secret**
3. **Use your own wallet addresses** (addresses you control)

---

## 🔧 Troubleshooting

- **"Missing environment variable"**: Check `.env` file has all required variables
- **"MongoDB connection failed"**: Make sure MongoDB is running (if local)
- **"Invalid bot token"**: Double-check your TELEGRAM_TOKEN


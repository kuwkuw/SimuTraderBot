# Railway Deployment Guide

## 🚀 Deploying Your Telegram Bot to Railway

### Prerequisites
1. Railway account (sign up at [railway.app](https://railway.app))
2. Telegram Bot Token from [@BotFather](https://t.me/BotFather)
3. OpenAI API Key (optional, for AI analysis feature)

### Step 1: Environment Variables Setup

In your Railway project dashboard, go to **Variables** tab and add these environment variables:

#### Required Variables:
```
BOT_TOKEN=your_telegram_bot_token_here
```

#### Optional Variables:
```
OPENAI_API_KEY=your_openai_api_key_here
```

> **Note:** The bot will work without OpenAI API key, but the `/analyze` command will be disabled.

### Step 2: Getting Your Bot Token

1. Open Telegram and find [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the token that looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
5. Add this token as `BOT_TOKEN` in Railway variables

### Step 3: Getting OpenAI API Key (Optional)

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create an account or sign in
3. Create a new API key
4. Copy the key that starts with `sk-`
5. Add this key as `OPENAI_API_KEY` in Railway variables

### Step 4: Deploy

1. Connect your GitHub repository to Railway
2. Railway will automatically detect `requirements.txt` and `runtime.txt`
3. The bot will start automatically after successful build

### Step 5: Verify Deployment

Check the Railway logs to see:
- ✅ "OpenAI client initialized successfully" (if API key provided)
- ⚠️ "OPENAI_API_KEY not found. AI analysis feature will be disabled." (if no API key)
- Bot should start polling for messages

### Common Issues & Solutions

#### Issue: "BOT_TOKEN environment variable is required"
**Solution:** Make sure you've added the `BOT_TOKEN` variable in Railway dashboard.

#### Issue: OpenAI errors
**Solution:** 
- The bot will work without OpenAI
- Verify your API key is correct
- Check if you have credits in your OpenAI account

#### Issue: Bot not responding
**Solution:**
- Check Railway logs for errors
- Verify your bot token with [@BotFather](https://t.me/BotFather)
- Make sure the bot is not running elsewhere

### Testing Your Bot

1. Find your bot on Telegram using the username you created
2. Send `/start` to initialize
3. Try commands like:
   - `/help` - Show available commands
   - `/balance` - Check your balance
   - `/buy bitcoin 0.1` - Test buying
   - `/trend bitcoin` - Test chart generation
   - `/analyze` - Test AI analysis (if OpenAI configured)

### Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Initialize account | `/start` |
| `/help` | Show help | `/help` |
| `/balance` | Check balance | `/balance` |
| `/buy` | Buy cryptocurrency | `/buy bitcoin 0.1` |
| `/sell` | Sell cryptocurrency | `/sell ethereum 0.5` |
| `/portfolio` | View portfolio | `/portfolio` |
| `/history` | Trading history | `/history` |
| `/trend` | Price chart | `/trend bitcoin` |
| `/analyze` | AI analysis | `/analyze` |

### Supported Cryptocurrencies

The bot uses CoinGecko API, so you can trade any cryptocurrency available there. Popular symbols:
- `bitcoin`
- `ethereum`
- `cardano`
- `polkadot`
- `chainlink`
- `litecoin`
- `dogecoin`

### Support

If you encounter issues:
1. Check Railway deployment logs
2. Verify all environment variables are set correctly
3. Test your bot token manually with Telegram API
4. Check CoinGecko API status

### Security Notes

- Never commit API keys to your repository
- Use Railway's environment variables feature
- Regularly rotate your API keys
- Monitor your OpenAI usage and costs

---

🎉 **Your trading bot is now live on Railway!** 

Share it with friends and start your crypto trading simulation journey!
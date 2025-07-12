# Railway Deployment Guide

## Environment Variables Setup

To fix the deployment errors, you need to set the following environment variables in your Railway project:

### Required Variables:
1. **BOT_TOKEN** - Your Telegram bot token from @BotFather
2. **OPENAI_API_KEY** - Your OpenAI API key from OpenAI platform

### How to Set Environment Variables in Railway:

1. **Open your Railway project dashboard**
2. **Go to the Variables tab**
3. **Add the following variables:**
   - Name: `BOT_TOKEN`
     Value: `your_telegram_bot_token_here`
   - Name: `OPENAI_API_KEY`
     Value: `your_openai_api_key_here`

### Getting Your API Keys:

#### Telegram Bot Token:
1. Message @BotFather on Telegram
2. Send `/newbot` command
3. Follow the instructions to create a new bot
4. Copy the bot token provided

#### OpenAI API Key:
1. Go to https://platform.openai.com/
2. Sign up/login to your account
3. Navigate to API Keys section
4. Create a new secret key
5. Copy the key (keep it secure!)

## Code Changes Made:

✅ **Fixed**: Added proper error handling for missing environment variables
✅ **Fixed**: OpenAI client now initializes safely with fallback when API key is missing
✅ **Fixed**: AI analysis feature gracefully handles missing OpenAI configuration
✅ **Fixed**: Better logging and error messages for troubleshooting

## Deployment Steps:

1. Set the environment variables in Railway dashboard
2. Redeploy your application
3. Check the logs to confirm successful initialization
4. Test the bot functionality

## Testing:

After deployment, test these commands:
- `/start` - Should work (no API key needed)
- `/balance` - Should work (no API key needed)
- `/analyze` - Will show "service unavailable" message if OpenAI key is missing

## Security Notes:

⚠️ **Never commit API keys to your repository**
⚠️ **Use Railway's environment variables for all secrets**
⚠️ **Keep your API keys secure and private**
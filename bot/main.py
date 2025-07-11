import logging
import os
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ParseMode
from dotenv import load_dotenv
import openai

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
openai.api_key = OPENAI_API_KEY

# SQLite DB setup
conn = sqlite3.connect("trading.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 10000.0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS portfolio (
    user_id INTEGER,
    symbol TEXT,
    amount REAL,
    PRIMARY KEY (user_id, symbol)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    user_id INTEGER,
    action TEXT,
    symbol TEXT,
    amount REAL,
    price REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()


# Get current crypto price from CoinGecko
async def get_price(symbol: str) -> float:
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data.get(symbol.lower(), {}).get("usd", 0)


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    await message.answer("👋 Вітаю в симуляторі криптотрейдингу! Ваш баланс: $10,000")


@dp.message_handler(commands=["balance"])
async def balance(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    bal = cursor.fetchone()[0]
    await message.answer(f"💰 Ваш поточний баланс: ${bal:.2f}")


@dp.message_handler(commands=["buy", "sell"])
async def trade(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("⚠️ Формат: /buy BTC 0.1 або /sell ETH 0.2")
    
    action, symbol, amount = parts
    amount = float(amount)
    symbol = symbol.upper()
    price = await get_price(symbol)
    if not price:
        return await message.reply("⚠️ Невідома монета або немає ціни.")

    cost = amount * price
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    bal = cursor.fetchone()[0]

    if action == "/buy":
        if bal < cost:
            return await message.reply("❌ Недостатньо коштів.")
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (cost, user_id))
        cursor.execute("INSERT OR IGNORE INTO portfolio (user_id, symbol, amount) VALUES (?, ?, 0)", (user_id, symbol))
        cursor.execute("UPDATE portfolio SET amount = amount + ? WHERE user_id=? AND symbol=?", (amount, user_id, symbol))
    elif action == "/sell":
        cursor.execute("SELECT amount FROM portfolio WHERE user_id=? AND symbol=?", (user_id, symbol))
        result = cursor.fetchone()
        if not result or result[0] < amount:
            return await message.reply("❌ Недостатньо активу для продажу.")
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (cost, user_id))
        cursor.execute("UPDATE portfolio SET amount = amount - ? WHERE user_id=? AND symbol=?", (amount, user_id, symbol))

    cursor.execute("INSERT INTO history (user_id, action, symbol, amount, price) VALUES (?, ?, ?, ?, ?)",
                   (user_id, action[1:], symbol, amount, price))
    conn.commit()
    await message.answer(f"✅ {action[1:].capitalize()} {amount} {symbol} по ціні ${price:.2f}")


@dp.message_handler(commands=["portfolio"])
async def portfolio(message: types.Message):
    user_id = message.from_user.id
    cursor.execute
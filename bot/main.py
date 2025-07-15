import logging
import os
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv
import requests
import io
import matplotlib.pyplot as plt
from aiogram.types import InputFile

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# DB
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

# 🔄 API CoinGecko

SYMBOL_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "doge": "dogecoin",
    "dot": "polkadot",
    "bnb": "binancecoin"
}

async def get_price(symbol: str) -> float:
    symbol_id = SYMBOL_MAP.get(symbol.lower())
    if not symbol_id:
        raise ValueError("Невідомий символ монети")

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol_id}&vs_currencies=usd"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get(symbol_id, {}).get("usd", 0)
                else:
                    return 0
    except Exception as e:
        logging.error(f"Error fetching price for {symbol}: {e}")
        return 0



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
    result = cursor.fetchone()
    if result:
        bal = result[0]
        await message.answer(f"💰 Баланс: ${bal:.2f}")
    else:
        await message.answer("❌ Користувача не знайдено. Використайте /start для початку.")


@dp.message_handler(commands=["buy", "sell"])
async def trade(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("⚠️ Формат: /buy BTC 0.1 або /sell ETH 0.2")
    
    action, symbol, amount_str = parts
    try:
        amount = float(amount_str)
        if amount <= 0:
            return await message.reply("⚠️ Кількість повинна бути більше 0.")
    except ValueError:
        return await message.reply("⚠️ Невірний формат кількості.")
    
    symbol = symbol.lower()
    price = await get_price(symbol)
    if not price:
        return await message.reply("⚠️ Невідома монета або немає ціни.")

    cost = amount * price
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return await message.reply("❌ Користувача не знайдено. Використайте /start для початку.")
    bal = result[0]

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
    await message.answer(f"✅ {action[1:].capitalize()} {amount} {symbol.upper()} по ${price:.2f}")


@dp.message_handler(commands=["portfolio"])
async def portfolio(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT symbol, amount FROM portfolio WHERE user_id=? AND amount > 0", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("📦 Портфель порожній.")
    lines = [f"{symbol}: {amt:.4f}" for symbol, amt in rows]
    await message.answer("📊 Портфель:\n" + "\n".join(lines))


@dp.message_handler(commands=["history"])
async def history(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT action, symbol, amount, price, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("⛔ Історія порожня.")
    text = "\n".join([f"{a.upper()} {s} {amt} @ ${p:.2f} [{t}]" for a, s, amt, p, t in rows])
    await message.answer("📜 Останні угоди:\n" + text)


@dp.message_handler(commands=["analyze"])
async def analyze(message: types.Message):
    if not GEMINI_API_KEY:
        await message.answer("❌ AI-аналіз недоступний. Сервіс налаштовується.")
        return
        
    user_id = message.from_user.id
    cursor.execute("SELECT action, symbol, amount, price, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("⛔ Немає угод для аналізу.")

    prompt = "Оціни трейдингові угоди користувача:\n\n"
    for action, symbol, amount, price, timestamp in rows:
        prompt += f"{timestamp}: {action.upper()} {amount} {symbol} по ціні ${price:.2f}\n"

    # Gemini API call
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    data = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    }
    try:
        response = requests.post(url, headers=headers, params=params, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        advice = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        await message.answer(f"🧠 AI-аналіз:\n\n{advice}")
    except Exception as e:
        logging.error(f"Gemini API error: {e}")
        await message.answer("❌ Не вдалося отримати аналіз від AI. Спробуйте пізніше.")


@dp.message_handler(commands=["trend"])
async def trend(message: types.Message):
    parts = message.text.strip().split()
    if len(parts) != 2:
        return await message.reply("⚠️ Формат: /trend BTC")

    symbol = parts[1].lower()
    try:
        chart = await get_trend_plot(symbol)
        await message.answer_photo(chart, caption=f"📈 Тренд {symbol.upper()} за 7 днів")
    except Exception as e:
        print(e)
        await message.reply("❌ Не вдалося побудувати графік. Можливо, монета неправильна.")

async def get_trend_plot(symbol: str) -> InputFile:
    symbol_id = SYMBOL_MAP.get(symbol.lower())
    if not symbol_id:
        raise ValueError("Невідомий символ монети")
    url = f"https://api.coingecko.com/api/v3/coins/{symbol_id}/market_chart?vs_currency=usd&days=7"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()

    prices = data.get("prices", [])
    if not prices:
        raise ValueError("Не вдалося отримати дані")

    dates = [p[0] / 1000 for p in prices]  # UNIX ms to s
    values = [p[1] for p in prices]

    plt.figure(figsize=(6, 3))
    plt.plot(values, color="blue", linewidth=2)
    plt.title(f"{symbol.upper()} / USD — 7 днів")
    plt.grid(True)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return InputFile(buf, filename=f"{symbol}_trend.png")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)

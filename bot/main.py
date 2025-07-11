import logging
import os
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv
from openai import OpenAI
import io
import matplotlib.pyplot as plt
from aiogram.types import InputFile

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Initialize bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Initialize OpenAI client only if API key is provided
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logging.info("OpenAI client initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize OpenAI client: {e}")
        openai_client = None
else:
    logging.warning("OPENAI_API_KEY not provided - AI analysis features will be disabled")

# DB - Support both PostgreSQL (Railway) and SQLite (local)
if DATABASE_URL:
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    logging.info("Connected to PostgreSQL database")
else:
    # Local SQLite fallback
    conn = sqlite3.connect("trading.db", check_same_thread=False)
    cursor = conn.cursor()
    logging.info("Connected to SQLite database")

# Create tables (compatible with both SQLite and PostgreSQL)
if DATABASE_URL:
    # PostgreSQL syntax
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        balance DECIMAL(15,2) DEFAULT 10000.0
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        user_id BIGINT,
        symbol VARCHAR(20),
        amount DECIMAL(15,8),
        PRIMARY KEY (user_id, symbol)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        user_id BIGINT,
        action VARCHAR(10),
        symbol VARCHAR(20),
        amount DECIMAL(15,8),
        price DECIMAL(15,2),
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
else:
    # SQLite syntax
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
async def get_price(symbol: str) -> float:
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data.get(symbol.lower(), {}).get("usd", 0)



@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    user_id = message.from_user.id
    if DATABASE_URL:
        cursor.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    else:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    await message.answer("👋 Вітаю в симуляторі криптотрейдингу! Ваш баланс: $10,000")


@dp.message_handler(commands=["balance"])
async def balance(message: types.Message):
    user_id = message.from_user.id
    if DATABASE_URL:
        cursor.execute("SELECT balance FROM users WHERE user_id=%s", (user_id,))
    else:
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    bal = cursor.fetchone()[0]
    await message.answer(f"💰 Баланс: ${bal:.2f}")


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
    
    # Get user balance
    if DATABASE_URL:
        cursor.execute("SELECT balance FROM users WHERE user_id=%s", (user_id,))
    else:
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    bal = cursor.fetchone()[0]

    if action == "/buy":
        if bal < cost:
            return await message.reply("❌ Недостатньо коштів.")
        
        if DATABASE_URL:
            cursor.execute("UPDATE users SET balance = balance - %s WHERE user_id=%s", (cost, user_id))
            cursor.execute("INSERT INTO portfolio (user_id, symbol, amount) VALUES (%s, %s, 0) ON CONFLICT (user_id, symbol) DO NOTHING", (user_id, symbol))
            cursor.execute("UPDATE portfolio SET amount = amount + %s WHERE user_id=%s AND symbol=%s", (amount, user_id, symbol))
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (cost, user_id))
            cursor.execute("INSERT OR IGNORE INTO portfolio (user_id, symbol, amount) VALUES (?, ?, 0)", (user_id, symbol))
            cursor.execute("UPDATE portfolio SET amount = amount + ? WHERE user_id=? AND symbol=?", (amount, user_id, symbol))
            
    elif action == "/sell":
        if DATABASE_URL:
            cursor.execute("SELECT amount FROM portfolio WHERE user_id=%s AND symbol=%s", (user_id, symbol))
        else:
            cursor.execute("SELECT amount FROM portfolio WHERE user_id=? AND symbol=?", (user_id, symbol))
            
        result = cursor.fetchone()
        if not result or result[0] < amount:
            return await message.reply("❌ Недостатньо активу для продажу.")
            
        if DATABASE_URL:
            cursor.execute("UPDATE users SET balance = balance + %s WHERE user_id=%s", (cost, user_id))
            cursor.execute("UPDATE portfolio SET amount = amount - %s WHERE user_id=%s AND symbol=%s", (amount, user_id, symbol))
        else:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (cost, user_id))
            cursor.execute("UPDATE portfolio SET amount = amount - ? WHERE user_id=? AND symbol=?", (amount, user_id, symbol))

    # Insert into history
    if DATABASE_URL:
        cursor.execute("INSERT INTO history (user_id, action, symbol, amount, price) VALUES (%s, %s, %s, %s, %s)",
                       (user_id, action[1:], symbol, amount, price))
    else:
        cursor.execute("INSERT INTO history (user_id, action, symbol, amount, price) VALUES (?, ?, ?, ?, ?)",
                       (user_id, action[1:], symbol, amount, price))
    conn.commit()
    await message.answer(f"✅ {action[1:].capitalize()} {amount} {symbol} по ${price:.2f}")


@dp.message_handler(commands=["portfolio"])
async def portfolio(message: types.Message):
    user_id = message.from_user.id
    if DATABASE_URL:
        cursor.execute("SELECT symbol, amount FROM portfolio WHERE user_id=%s AND amount > 0", (user_id,))
    else:
        cursor.execute("SELECT symbol, amount FROM portfolio WHERE user_id=? AND amount > 0", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("📦 Портфель порожній.")
    lines = [f"{symbol}: {amt:.4f}" for symbol, amt in rows]
    await message.answer("📊 Портфель:\n" + "\n".join(lines))


@dp.message_handler(commands=["history"])
async def history(message: types.Message):
    user_id = message.from_user.id
    if DATABASE_URL:
        cursor.execute("SELECT action, symbol, amount, price, timestamp FROM history WHERE user_id=%s ORDER BY timestamp DESC LIMIT 10", (user_id,))
    else:
        cursor.execute("SELECT action, symbol, amount, price, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("⛔ Історія порожня.")
    text = "\n".join([f"{a.upper()} {s} {amt} @ ${p:.2f} [{t}]" for a, s, amt, p, t in rows])
    await message.answer("📜 Останні угоди:\n" + text)


@dp.message_handler(commands=["analyze"])
async def analyze(message: types.Message):
    # Check if OpenAI is available
    if not openai_client:
        return await message.answer("❌ AI-аналіз недоступний. OpenAI API ключ не налаштований.")
    
    user_id = message.from_user.id
    
    # Use appropriate placeholder for SQL
    if DATABASE_URL:
        cursor.execute("SELECT action, symbol, amount, price, timestamp FROM history WHERE user_id=%s ORDER BY timestamp DESC LIMIT 10", (user_id,))
    else:
        cursor.execute("SELECT action, symbol, amount, price, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (user_id,))
    
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("⛔ Немає угод для аналізу.")

    prompt = "Оціни трейдингові угоди користувача:\n\n"
    for action, symbol, amount, price, timestamp in rows:
        prompt += f"{timestamp}: {action.upper()} {amount} {symbol} по ціні ${price:.2f}\n"

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ти криптоаналітик. Аналізуй дії користувача і давай поради."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )

        advice = response.choices[0].message.content.strip()
        await message.answer(f"🧠 AI-аналіз:\n\n{advice}")
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        await message.answer("❌ Помилка при отриманні AI-аналізу. Спробуйте пізніше.")


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
        logging.error(f"Trend plot error: {e}")
        await message.reply("❌ Не вдалося побудувати графік. Можливо, монета неправильна.")


async def get_trend_plot(symbol: str) -> InputFile:
    url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}/market_chart?vs_currency=usd&days=7"
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

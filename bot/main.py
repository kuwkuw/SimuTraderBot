import logging
import os
import sqlite3
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv
from openai import OpenAI
import io
import matplotlib.pyplot as plt
from aiogram.types import InputFile
import contextlib
from decimal import Decimal, InvalidOperation
import time
from functools import wraps

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate environment variables
def validate_environment():
    required_vars = ["BOT_TOKEN", "OPENAI_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

validate_environment()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Rate limiting
user_last_request = {}
RATE_LIMIT_SECONDS = 2

async def rate_limit(user_id: int):
    now = time.time()
    if user_id in user_last_request:
        time_diff = now - user_last_request[user_id]
        if time_diff < RATE_LIMIT_SECONDS:
            await asyncio.sleep(RATE_LIMIT_SECONDS - time_diff)
    user_last_request[user_id] = now

# Error handler decorator
def error_handler(func):
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        try:
            await rate_limit(message.from_user.id)
            return await func(message, *args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {e}", exc_info=True)
            await message.reply("⚠️ Виникла помилка. Спробуйте пізніше.")
    return wrapper

# Input validation
def validate_trade_amount(amount_str: str) -> Decimal:
    try:
        amount = Decimal(amount_str)
        if amount <= 0 or amount > Decimal('1000000'):
            raise ValueError("Amount out of range")
        return amount
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid amount: {amount_str}")

def validate_symbol(symbol: str) -> str:
    if not symbol or len(symbol) > 10 or not symbol.isalnum():
        raise ValueError(f"Invalid symbol: {symbol}")
    return symbol.upper()

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
    PRIMARY KEY (user_id, symbol),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    user_id INTEGER,
    action TEXT,
    symbol TEXT,
    amount REAL,
    price REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
""")

# Create indexes for performance
cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_user_symbol ON portfolio(user_id, symbol)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user_timestamp ON history(user_id, timestamp DESC)")
conn.commit()

# Database transaction helper
@contextlib.asynccontextmanager
async def db_transaction():
    try:
        cursor.execute("BEGIN IMMEDIATE")
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise

# 🔄 API CoinGecko
async def get_price(symbol: str) -> float:
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return 0
                data = await resp.json()
                price = data.get(symbol.lower(), {}).get("usd", 0)
                return float(price) if price else 0
    except Exception as e:
        logging.error(f"Error fetching price for {symbol}: {e}")
        return 0



@dp.message_handler(commands=["start"])
@error_handler
async def start(message: types.Message):
    user_id = message.from_user.id
    async with db_transaction() as tx:
        tx.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    await message.answer("👋 Вітаю в симуляторі криптотрейдингу! Ваш баланс: $10,000")


@dp.message_handler(commands=["balance"])
@error_handler
async def balance(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result is None:
        # User not found, create them
        async with db_transaction() as tx:
            tx.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        bal = 10000.0
    else:
        bal = result[0]
    await message.answer(f"💰 Баланс: ${bal:.2f}")


@dp.message_handler(commands=["buy", "sell"])
@error_handler
async def trade(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("⚠️ Формат: /buy BTC 0.1 або /sell ETH 0.2")
    
    action, symbol_str, amount_str = parts
    
    # Validate inputs
    try:
        symbol = validate_symbol(symbol_str)
        amount = validate_trade_amount(amount_str)
    except ValueError as e:
        return await message.reply(f"⚠️ {str(e)}")
    
    # Get current price
    price = await get_price(symbol)
    if not price:
        return await message.reply("⚠️ Невідома монета або немає ціни.")

    cost = amount * Decimal(str(price))
    
    # Execute trade in atomic transaction
    try:
        async with db_transaction() as tx:
            # Ensure user exists
            tx.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            
            # Get current balance with lock
            tx.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            result = tx.fetchone()
            current_balance = Decimal(str(result[0])) if result else Decimal('10000.0')

            if action == "/buy":
                if current_balance < cost:
                    return await message.reply("❌ Недостатньо коштів.")
                
                # Update balance
                new_balance = current_balance - cost
                tx.execute("UPDATE users SET balance = ? WHERE user_id=?", (float(new_balance), user_id))
                
                # Update portfolio
                tx.execute("INSERT OR IGNORE INTO portfolio (user_id, symbol, amount) VALUES (?, ?, 0)", (user_id, symbol))
                tx.execute("UPDATE portfolio SET amount = amount + ? WHERE user_id=? AND symbol=?", 
                          (float(amount), user_id, symbol))
                
            elif action == "/sell":
                # Check portfolio holdings
                tx.execute("SELECT amount FROM portfolio WHERE user_id=? AND symbol=?", (user_id, symbol))
                portfolio_result = tx.fetchone()
                current_amount = Decimal(str(portfolio_result[0])) if portfolio_result else Decimal('0')
                
                if current_amount < amount:
                    return await message.reply("❌ Недостатньо активу для продажу.")
                
                # Update balance and portfolio
                new_balance = current_balance + cost
                tx.execute("UPDATE users SET balance = ? WHERE user_id=?", (float(new_balance), user_id))
                tx.execute("UPDATE portfolio SET amount = amount - ? WHERE user_id=? AND symbol=?", 
                          (float(amount), user_id, symbol))

            # Record transaction
            tx.execute("INSERT INTO history (user_id, action, symbol, amount, price) VALUES (?, ?, ?, ?, ?)",
                      (user_id, action[1:], symbol, float(amount), price))
                      
        await message.answer(f"✅ {action[1:].capitalize()} {amount} {symbol} по ${price:.2f}")
        
    except Exception as e:
        logging.error(f"Trade error for user {user_id}: {e}")
        await message.reply("❌ Помилка при виконанні угоди. Спробуйте ще раз.")


@dp.message_handler(commands=["portfolio"])
@error_handler
async def portfolio(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT symbol, amount FROM portfolio WHERE user_id=? AND amount > 0", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("📦 Портфель порожній.")
    lines = [f"{symbol}: {amt:.4f}" for symbol, amt in rows]
    await message.answer("📊 Портфель:\n" + "\n".join(lines))


@dp.message_handler(commands=["history"])
@error_handler
async def history(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT action, symbol, amount, price, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("⛔ Історія порожня.")
    text = "\n".join([f"{a.upper()} {s} {amt} @ ${p:.2f} [{t}]" for a, s, amt, p, t in rows])
    await message.answer("📜 Останні угоди:\n" + text)


@dp.message_handler(commands=["analyze"])
@error_handler
async def analyze(message: types.Message):
    user_id = message.from_user.id
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
        await message.answer("⚠️ Зараз аналіз недоступний. Спробуйте пізніше.")


@dp.message_handler(commands=["trend"])
@error_handler
async def trend(message: types.Message):
    parts = message.text.strip().split()
    if len(parts) != 2:
        return await message.reply("⚠️ Формат: /trend BTC")

    symbol_str = parts[1]
    try:
        symbol = validate_symbol(symbol_str)
        chart = await get_trend_plot(symbol.lower())
        await message.answer_photo(chart, caption=f"📈 Тренд {symbol.upper()} за 7 днів")
    except ValueError as e:
        await message.reply(f"⚠️ {str(e)}")
    except Exception as e:
        logging.error(f"Trend chart error: {e}")
        await message.reply("❌ Не вдалося побудувати графік. Можливо, монета неправильна.")

async def get_trend_plot(symbol: str) -> InputFile:
    url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}/market_chart?vs_currency=usd&days=7"
    
    # Fetch data with timeout
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise ValueError("Не вдалося отримати дані для цієї монети")
                data = await resp.json()
    except Exception:
        raise ValueError("Помилка при отриманні даних")

    prices = data.get("prices", [])
    if not prices:
        raise ValueError("Немає даних для побудови графіка")

    # Use proper context management for matplotlib
    fig, ax = plt.subplots(figsize=(6, 3))
    try:
        dates = [p[0] / 1000 for p in prices]  # UNIX ms to s
        values = [p[1] for p in prices]

        ax.plot(values, color="blue", linewidth=2)
        ax.set_title(f"{symbol.upper()} / USD — 7 днів")
        ax.grid(True)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=80, bbox_inches='tight')
        buf.seek(0)
        
        return InputFile(buf, filename=f"{symbol}_trend.png")
    finally:
        # Ensure figure is always closed to prevent memory leaks
        plt.close(fig)


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )
    
    logging.info("Starting SimuTraderBot...")
    executor.start_polling(dp, skip_updates=True)

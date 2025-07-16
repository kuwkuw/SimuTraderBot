import sqlite3
from typing import Optional, List, Tuple

DB_PATH = "trading.db"

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Database setup
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

# User functions
def add_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def get_balance(user_id: int) -> Optional[float]:
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def update_balance(user_id: int, amount: float):
    cursor.execute("UPDATE users SET balance = ? WHERE user_id=?", (amount, user_id))
    conn.commit()

# Portfolio functions
def get_portfolio(user_id: int) -> List[Tuple[str, float]]:
    cursor.execute("SELECT symbol, amount FROM portfolio WHERE user_id=? AND amount > 0", (user_id,))
    return cursor.fetchall()

def add_to_portfolio(user_id: int, symbol: str, amount: float):
    cursor.execute("INSERT OR IGNORE INTO portfolio (user_id, symbol, amount) VALUES (?, ?, 0)", (user_id, symbol))
    cursor.execute("UPDATE portfolio SET amount = amount + ? WHERE user_id=? AND symbol=?", (amount, user_id, symbol))
    conn.commit()

def remove_from_portfolio(user_id: int, symbol: str, amount: float):
    cursor.execute("UPDATE portfolio SET amount = amount - ? WHERE user_id=? AND symbol=?", (amount, user_id, symbol))
    conn.commit()

def get_portfolio_amount(user_id: int, symbol: str) -> Optional[float]:
    cursor.execute("SELECT amount FROM portfolio WHERE user_id=? AND symbol=?", (user_id, symbol))
    result = cursor.fetchone()
    return result[0] if result else None

# History functions
def add_history(user_id: int, action: str, symbol: str, amount: float, price: float):
    cursor.execute("INSERT INTO history (user_id, action, symbol, amount, price) VALUES (?, ?, ?, ?, ?)",
                   (user_id, action, symbol, amount, price))
    conn.commit()

def get_history(user_id: int, limit: int = 10) -> List[Tuple[str, str, float, float, str]]:
    cursor.execute("SELECT action, symbol, amount, price, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    return cursor.fetchall() 
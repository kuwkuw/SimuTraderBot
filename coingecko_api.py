import aiohttp
import io
import matplotlib.pyplot as plt
from aiogram.types import InputFile
from typing import List, Tuple

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
        print(f"Error fetching price for {symbol}: {e}")
        return 0

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
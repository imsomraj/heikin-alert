import ccxt
import asyncio
import os
from telegram import Bot

# ========== CONFIG (ENV VARIABLES) ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = [
    "BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","DOGE/USDT","BNB/USDT"
]

TIMEFRAMES = ["45m","1h","4h","1d"]

POLL_INTERVAL = 60  # seconds
OPEN_EQUAL_TOL = 0.0005  # 0.05% tolerance
# ============================================

exchange = ccxt.bybit({
    "enableRateLimit": True
})
bot = Bot(BOT_TOKEN)

# Prevent duplicate alerts
sent_alerts = set()

# ---------- HEIKIN ASHI ----------
def heikin_ashi(candles):
    ha = []
    for i, c in enumerate(candles):
        o, h, l, cl = c[1], c[2], c[3], c[4]

        ha_close = (o + h + l + cl) / 4
        ha_open = (o + cl) / 2 if i == 0 else (ha[i-1]["open"] + ha[i-1]["close"]) / 2

        ha.append({
            "open": ha_open,
            "close": ha_close,
            "high": max(h, ha_open, ha_close),
            "low": min(l, ha_open, ha_close)
        })
    return ha

# ---------- REAL DOJI ----------
def is_real_doji(c):
    o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
    rng = h - l
    if rng == 0:
        return False

    body = abs(cl - o)
    upper = h - max(o, cl)
    lower = min(o, cl) - l

    body_ok = body <= rng * 0.05
    wick_ok = abs(upper - lower) <= rng * 0.10
    center_ok = abs(((o + cl) / 2) - ((h + l) / 2)) <= rng * 0.10

    return body_ok and wick_ok and center_ok

# ---------- HELPERS ----------
def approx_equal(a, b):
    return abs(a - b) <= a * OPEN_EQUAL_TOL

# ---------- MAIN LOOP ----------
async def scan():
    await bot.send_message(CHAT_ID, "🤖 Heikin Ashi Bot started (Railway)")

    while True:
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                try:
                    candles = exchange.fetch_ohlcv(symbol, tf, limit=5)
                    ha = heikin_ashi(candles)

                    d0, d1, d2 = ha[-3], ha[-2], ha[-1]
                    key = f"{symbol}-{tf}-{candles[-2][0]}"

                    if key in sent_alerts:
                        continue

                    if not is_real_doji(d0):
                        continue

                    # BUY SETUP
                    if d1["close"] > d1["open"] and approx_equal(d1["open"], d1["low"]):
                        sent_alerts.add(key)
                        await bot.send_message(
                            CHAT_ID,
                            f"🟢 BUY SETUP\n{symbol} {tf}\nDoji + Open≈Low"
                        )

                    # SELL SETUP
                    if d1["close"] < d1["open"] and approx_equal(d1["open"], d1["high"]):
                        sent_alerts.add(key)
                        await bot.send_message(
                            CHAT_ID,
                            f"🔴 SELL SETUP\n{symbol} {tf}\nDoji + Open≈High"
                        )

                except Exception as e:
                    print("Error:", symbol, tf, e)

        await asyncio.sleep(POLL_INTERVAL)

# ---------- RUN ----------
if __name__ == "__main__":
    asyncio.run(scan())

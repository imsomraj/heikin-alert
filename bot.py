import ccxt
import asyncio
import os
from telegram import Bot

# ========== CONFIG (ENV VARIABLES) ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT"
]

TIMEFRAMES = ["1h","4h","12h","1d"]

POLL_INTERVAL = 60  # seconds
OPEN_EQUAL_TOL = 0.0005  # 0.05% tolerance
# ============================================

exchange = ccxt.okx({
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"   # USDT perpetual futures
    }
})
exchange.load_markets()
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
        return False, 0.0

    body = abs(cl - o)
    body_ratio = body / rng

    return body_ratio <= 0.02, body_ratio * 100

# ---------- HELPERS ----------
def approx_equal(a, b):
    return abs(a - b) <= a * OPEN_EQUAL_TOL

# ---------- MAIN LOOP ----------
async def scan():
    await bot.send_message(CHAT_ID, "🤖 Heikin Ashi Bot started (FINAL LOGIC)")

    while True:
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                try:
                    candles = exchange.fetch_ohlcv(symbol, tf, limit=100)
                    ha = heikin_ashi(candles)

                    d0 = ha[-3]  # Doji candle (closed)
                    d1 = ha[-2]  # Setup candle (closed)
                    d2 = ha[-1]  # Live candle

                    doji_key = f"DOJI-{symbol}-{tf}-{candles[-3][0]}"
                    setup_key = f"SETUP-{symbol}-{tf}-{candles[-2][0]}"

                    # -------- DOJI CHECK --------
                    is_doji, body_pct = is_real_doji(d0)

                    if is_doji and doji_key not in sent_alerts:
                        sent_alerts.add(doji_key)
                        await bot.send_message(
                            CHAT_ID,
                            f"🟡 DOJI FORMED\n"
                            f"{symbol} {tf}\n"
                            f"O={d0['open']:.4f} "
                            f"H={d0['high']:.4f} "
                            f"L={d0['low']:.4f} "
                            f"C={d0['close']:.4f}\n"
                            f"Body% = {body_pct:.2f}%"
                        )

                    # ❌ NO DOJI → NO SETUP (THIS IS THE FIX)
                    if not is_doji:
                        continue

                    # -------- LONG SETUP --------
                    if (
                        d1["close"] > d1["open"] and
                        approx_equal(d1["open"], d1["low"]) and
                        setup_key not in sent_alerts
                    ):
                        sent_alerts.add(setup_key)
                        await bot.send_message(
                            CHAT_ID,
                            f"🟢 LONG SETUP\n"
                            f"{symbol} {tf}\n"
                            f"Doji → Open≈Low"
                        )

                    # -------- SHORT SETUP --------
                    if (
                        d1["close"] < d1["open"] and
                        approx_equal(d1["open"], d1["high"]) and
                        setup_key not in sent_alerts
                    ):
                        sent_alerts.add(setup_key)
                        await bot.send_message(
                            CHAT_ID,
                            f"🔴 SHORT SETUP\n"
                            f"{symbol} {tf}\n"
                            f"Doji → Open≈High"
                        )

                except Exception as e:
                    print("Error:", symbol, tf, e)

        await asyncio.sleep(POLL_INTERVAL)

# ---------- RUN ----------
if __name__ == "__main__":
    asyncio.run(scan())

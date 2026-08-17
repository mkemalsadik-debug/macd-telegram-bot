import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd

# ==========================================
# AYARLAR
# ==========================================

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ETHFIUSDT",
    "AVAXUSDT",
    "HYPEUSDT",
    "LITUSDT",
]

TIMEFRAMES = {
    "2H": "2h",
    "4H": "4h",
    "12H": "12h",
    "1D": "1d",
}

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1921028034"

BINANCE_URL = "https://fapi.binance.com/fapi/v1/klines"
STATE_FILE = Path("state.json")

TURKEY_TZ = timezone(timedelta(hours=3))


# ==========================================
# TELEGRAM
# ==========================================

def send_telegram(message):
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN GitHub Secret bulunamadi.")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
        },
        timeout=15,
    )
    response.raise_for_status()


# ==========================================
# BINANCE FUTURES VERİSİ
# ==========================================

def get_data(symbol, interval):
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": 100,
    }

    response = requests.get(
        BINANCE_URL,
        params=params,
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()

    columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "taker_base",
        "taker_quote",
        "ignore",
    ]

    df = pd.DataFrame(data, columns=columns)

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df["close"] = df["close"].astype(float)

    return df


# ==========================================
# MACD
# ==========================================

def calculate_macd(df):
    ema_fast = df["close"].ewm(
        span=MACD_FAST,
        adjust=False
    ).mean()

    ema_slow = df["close"].ewm(
        span=MACD_SLOW,
        adjust=False
    ).mean()

    df["macd"] = ema_fast - ema_slow

    df["signal"] = df["macd"].ewm(
        span=MACD_SIGNAL,
        adjust=False
    ).mean()

    return df


# ==========================================
# CROSS KONTROLÜ
# ==========================================

def get_cross(previous, current):
    bullish = (
        previous["macd"] <= previous["signal"]
        and current["macd"] > current["signal"]
    )

    bearish = (
        previous["macd"] >= previous["signal"]
        and current["macd"] < current["signal"]
    )

    if bullish:
        return "BULLISH"

    if bearish:
        return "BEARISH"

    return None


# ==========================================
# HAFIZA
# ==========================================

def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ==========================================
# ZAMAN
# ==========================================

def turkey_time(dt):
    return dt.astimezone(TURKEY_TZ).strftime("%Y-%m-%d %H:%M:%S")


# ==========================================
# TEK ÇALIŞMA
# ==========================================

def main():
    print("==========================================")
    print("       BTC MACD TELEGRAM BOT")
    print("==========================================")
    print("Coin sayisi :", len(SYMBOLS))
    print("Coinler     :", ", ".join(SYMBOLS))
    print("Zamanlar    : 2H / 4H / 12H / 1D")
    print("MACD        : 12 / 26 / 9")
    print("Kontrol     : GitHub Actions / 5 dakika")
    print("Veri        : Binance Futures")
    print("🟢 Sadece kapanmis mum cross")
    print("==========================================")
    print()

    state = load_state()
    changed = False
    successful_requests = 0

    for symbol in SYMBOLS:
        for name, interval in TIMEFRAMES.items():
            try:
                df = calculate_macd(get_data(symbol, interval))
                successful_requests += 1

                # Son satır Binance'teki canlı mumdur.
                # [-2] son kapanmış, [-3] ondan önceki kapanmış mumdur.
                closed_candle = df.iloc[-2]
                previous_closed = df.iloc[-3]

                closed_time = closed_candle["open_time"]
                closed_key = closed_time.isoformat()

                cross = get_cross(previous_closed, closed_candle)

                state_key = f"{symbol}_{name}"
                last_alerted = state.get(state_key)

                if cross is not None and last_alerted != closed_key:
                    if cross == "BULLISH":
                        message = (
                            f"🟢 {symbol} {name}\n\n"
                            f"YUKARI CROSS\n"
                            f"✅ Mum kapandi.\n\n"
                            f"Mum: {turkey_time(closed_time)} (TR)"
                        )
                    else:
                        message = (
                            f"🔴 {symbol} {name}\n\n"
                            f"ASAGI CROSS\n"
                            f"✅ Mum kapandi.\n\n"
                            f"Mum: {turkey_time(closed_time)} (TR)"
                        )

                    send_telegram(message)

                    state[state_key] = closed_key
                    changed = True

                    print(
                        f"[{symbol} {name}] YENI CROSS:",
                        closed_time,
                        cross,
                    )

            except Exception as e:
                print(f"[{symbol} {name}] HATA:", e)

    # Sadece yeni bir sinyal olduğunda state değişir.
    # Böylece GitHub repository'sine gereksiz yere sürekli commit atmayız.
    if changed:
        save_state(state)
        print("State guncellendi.")
    else:
        print("Yeni cross yok.")

    print()
    print(f"Basarili Binance istekleri: {successful_requests}/40")
    print("Calisma tamamlandi.")


if __name__ == "__main__":
    main()

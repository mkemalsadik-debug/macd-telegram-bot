import os
import requests
import pandas as pd

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
    "LITUSDT"
]

TIMEFRAMES = {
    "2H": "2h",
    "4H": "4h",
    "12H": "12h",
    "1D": "1d"
}

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1921028034"

BINANCE_URL = "https://fapi.binance.com/fapi/v1/klines"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=10
    )


def get_data(symbol, interval):

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": 100
    }

    response = requests.get(
        BINANCE_URL,
        params=params,
        timeout=10
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
        "ignore"
    ]

    df = pd.DataFrame(data, columns=columns)

    df["close"] = df["close"].astype(float)

    return df


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


def check_cross(df):

    # -1 = halen oluşan mum
    # -2 = son kapanmış mum
    # -3 = ondan önceki kapanmış mum

    previous = df.iloc[-3]
    current = df.iloc[-2]

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


print("MACD kontrolü başladı.")

for symbol in SYMBOLS:

    for timeframe_name, interval in TIMEFRAMES.items():

        try:

            df = get_data(symbol, interval)
            df = calculate_macd(df)

            cross = check_cross(df)

            if cross:

                if cross == "BULLISH":
                    emoji = "🟢"
                else:
                    emoji = "🔴"

                message = (
                    f"{emoji} MACD CROSS\n\n"
                    f"Coin: {symbol}\n"
                    f"Zaman: {timeframe_name}\n"
                    f"Yön: {cross}\n"
                    f"MACD: {df.iloc[-2]['macd']:.6f}\n"
                    f"Signal: {df.iloc[-2]['signal']:.6f}"
                )

                send_telegram(message)

                print(
                    f"{emoji} {symbol} {timeframe_name} {cross}"
                )

            else:

                print(
                    f"Yok | {symbol} | {timeframe_name}"
                )

        except Exception as e:

            print(
                f"HATA | {symbol} | {timeframe_name} | {e}"
            )

print("MACD kontrolü tamamlandı.")

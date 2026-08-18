import os
import json
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

BINANCE_URL = "https://api-gcp.binance.com/api/v3/klines"

STATE_FILE = "state.json"


# ==========================================
# STATE
# ==========================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {}

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as e:

        print("State okunamadı:", e)
        return {}


def save_state(state):

    try:

        with open(
            STATE_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                state,
                file,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print("State kaydedilemedi:", e)


state = load_state()


# ==========================================
# TELEGRAM
# ==========================================

def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=10
    )

    response.raise_for_status()


# ==========================================
# BINANCE FUTURES VERİSİ
# ==========================================

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

    df = pd.DataFrame(
        data,
        columns=columns
    )

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
# KAPANMIŞ MUMDA CROSS KONTROLÜ
# ==========================================

def check_cross(df):

    # Son mum (-1) halen oluşuyor olabilir.
    # Bu nedenle sadece kapanmış mumları kullanıyoruz.

    previous = df.iloc[-3]
    current = df.iloc[-2]

    bullish = (
        previous["macd"] <= previous["signal"]
        and
        current["macd"] > current["signal"]
    )

    bearish = (
        previous["macd"] >= previous["signal"]
        and
        current["macd"] < current["signal"]
    )

    if bullish:
        return "BULLISH"

    if bearish:
        return "BEARISH"

    return None


# ==========================================
# ANA KONTROL
# ==========================================

print("==========================================")
print("MACD kontrolü başladı.")
print("==========================================")

for symbol in SYMBOLS:

    for timeframe_name, interval in TIMEFRAMES.items():

        try:

            # ----------------------------------
            # Binance verisini al
            # ----------------------------------

            df = get_data(
                symbol,
                interval
            )

            # ----------------------------------
            # MACD hesapla
            # ----------------------------------

            df = calculate_macd(df)

            # ----------------------------------
            # Kapanmış mumda cross kontrolü
            # ----------------------------------

            cross = check_cross(df)

            if cross:

                # Kapanmış cross mumunun zamanı
                candle_time = str(
                    df.iloc[-2]["open_time"]
                )

                # Her coin/timeframe için ayrı state
                state_key = (
                    f"{symbol}_{timeframe_name}"
                )

                # Bu cross'un benzersiz kimliği
                signal_id = (
                    f"{candle_time}_{cross}"
                )

                # Daha önce gönderilmiş mi?
                last_signal = state.get(
                    state_key
                )

                if last_signal == signal_id:

                    print(
                        f"Tekrar yok | "
                        f"{symbol} | "
                        f"{timeframe_name}"
                    )

                    continue

                # ----------------------------------
                # Yeni cross
                # ----------------------------------

                if cross == "BULLISH":

                    emoji = "🟢"

                else:

                    emoji = "🔴"

                message = (
                    f"{emoji} MACD CROSS\n\n"
                    f"Coin: {symbol}\n"
                    f"Zaman: {timeframe_name}\n"
                    f"Yön: {cross}\n"
                    f"MACD: "
                    f"{df.iloc[-2]['macd']:.6f}\n"
                    f"Signal: "
                    f"{df.iloc[-2]['signal']:.6f}"
                )

                # Telegram gönder
                send_telegram(message)

                print(
                    f"{emoji} "
                    f"{symbol} "
                    f"{timeframe_name} "
                    f"{cross}"
                )

                # Gönderilen cross'u kaydet
                state[state_key] = signal_id

                save_state(state)

            else:

                print(
                    f"Yok | "
                    f"{symbol} | "
                    f"{timeframe_name}"
                )

        except Exception as e:

            print(
                f"HATA | "
                f"{symbol} | "
                f"{timeframe_name} | "
                f"{e}"
            )


print("==========================================")
print("MACD kontrolü tamamlandı.")
print("==========================================")

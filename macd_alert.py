import os
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
    "2H": "120",
    "4H": "240",
    "12H": "720",
    "1D": "D"
}

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1921028034"

BYBIT_URL = "https://api.bybit.com/v5/market/kline"

STATE_FILE = "state.json"


# ==========================================
# TELEGRAM
# ==========================================

def send_telegram(message):

    if not TELEGRAM_TOKEN:
        raise Exception("TELEGRAM_TOKEN bulunamadi.")

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
# BYBIT PUBLIC API
# ==========================================

def get_data(symbol, interval):

    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": 100
    }

    response = requests.get(
        BYBIT_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if data.get("retCode") != 0:
        raise Exception(
            f"Bybit API: {data.get('retMsg')}"
        )

    candles = data["result"]["list"]

    if not candles:
        raise Exception("Mum verisi bos.")

    # Bybit en yeni mumu ilk sırada gönderiyor.
    # Eskiden yeniye sıralıyoruz.
    candles.reverse()

    df = pd.DataFrame(
        candles,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover"
        ]
    )

    df["open_time"] = pd.to_datetime(
        df["open_time"].astype("int64"),
        unit="ms"
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover"
    ]:
        df[column] = df[column].astype(float)

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
# SADECE KAPANMIŞ MUM
# ==========================================

def check_cross(df):

    # Bybit'in son satırı mevcut/açık mum olabilir.
    # -2 = son kapanmış mum
    # -3 = ondan önceki kapanmış mum

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
# STATE
# AYNI CROSS'U TEKRAR GÖNDERME
# ==========================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {}

    try:

        import json

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:

        return {}


def save_state(state):

    import json

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False
        )


# ==========================================
# ANA PROGRAM
# ==========================================

print("==========================================")
print("MACD TELEGRAM BOT")
print("==========================================")
print("Veri        : Bybit Public API")
print("Piyasa      : USDT Perpetual")
print("Coin sayisi : 10")
print("Zamanlar    : 2H / 4H / 12H / 1D")
print("MACD        : 12 / 26 / 9")
print("Sinyal      : Kapanmis mum")
print("Tekrar      : Engelli")
print("==========================================")
print()
print("MACD kontrolü başladı.")
print("==========================================")

state = load_state()
state_changed = False

for symbol in SYMBOLS:

    for timeframe_name, interval in TIMEFRAMES.items():

        try:

            df = get_data(
                symbol,
                interval
            )

            df = calculate_macd(df)

            cross = check_cross(df)

            # Kapanmış mumun zamanı
            candle_time = str(
                df.iloc[-2]["open_time"]
            )

            # Her coin + timeframe için
            # son gönderilen sinyali ayrı tutuyoruz.
            state_key = (
                f"{symbol}_{timeframe_name}"
            )

            signal_id = None

            if cross:

                signal_id = (
                    f"{candle_time}_{cross}"
                )

                last_signal = state.get(
                    state_key
                )

                # Daha önce gönderilmişse
                # tekrar Telegram gönderme.
                if signal_id == last_signal:

                    print(
                        f"Tekrar engellendi | "
                        f"{symbol} | "
                        f"{timeframe_name} | "
                        f"{cross}"
                    )

                else:

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
                        f"{df.iloc[-2]['signal']:.6f}\n\n"
                        f"Kaynak: Bybit"
                    )

                    send_telegram(message)

                    state[state_key] = signal_id
                    state_changed = True

                    print(
                        f"{emoji} {symbol} "
                        f"{timeframe_name} "
                        f"{cross}"
                    )

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


# ==========================================
# STATE KAYDET
# ==========================================

if state_changed:

    save_state(state)

    print()
    print("State güncellendi.")

else:

    print()
    print("State değişmedi.")


print("==========================================")
print("MACD kontrolü tamamlandı.")
print("==========================================")

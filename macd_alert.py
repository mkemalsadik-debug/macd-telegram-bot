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
    "2H": {
        "type": "hour",
        "aggregate": 2,
        "seconds": 2 * 60 * 60
    },
    "4H": {
        "type": "hour",
        "aggregate": 4,
        "seconds": 4 * 60 * 60
    },
    "12H": {
        "type": "hour",
        "aggregate": 12,
        "seconds": 12 * 60 * 60
    },
    "1D": {
        "type": "day",
        "aggregate": 1,
        "seconds": 24 * 60 * 60
    }
}

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1921028034"

CRYPTOCOMPARE_URL = "https://min-api.cryptocompare.com/data/v2"

STATE_FILE = "state.json"


# ==========================================
# STATE
# ==========================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}


def save_state(state):

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


state = load_state()


# ==========================================
# TELEGRAM
# ==========================================

def send_telegram(message):

    if not TELEGRAM_TOKEN:
        print("HATA | TELEGRAM_TOKEN bulunamadı.")
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    try:

        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=10
        )

        response.raise_for_status()

        return True

    except Exception as e:

        print(f"Telegram HATASI: {e}")

        return False


# ==========================================
# SEMBOL
# ==========================================

def split_symbol(symbol):

    # BTCUSDT -> BTC / USDT

    if symbol.endswith("USDT"):
        return symbol[:-4], "USDT"

    raise ValueError(
        f"Desteklenmeyen sembol: {symbol}"
    )


# ==========================================
# CRYPTOCOMPARE VERİSİ
# ==========================================

def get_data(symbol, timeframe):

    fsym, tsym = split_symbol(symbol)

    config = TIMEFRAMES[timeframe]

    params = {
        "fsym": fsym,
        "tsym": tsym,
        "e": "Binance",
        "limit": 100,
        "aggregate": config["aggregate"],
        "aggregatePredictableTimePeriods": "true"
    }

    if config["type"] == "hour":

        endpoint = f"{CRYPTOCOMPARE_URL}/histohour"

    else:

        endpoint = f"{CRYPTOCOMPARE_URL}/histoday"

    response = requests.get(
        endpoint,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    result = response.json()

    if result.get("Response") != "Success":

        raise RuntimeError(
            result.get(
                "Message",
                "CryptoCompare veri hatası"
            )
        )

    data = result.get("Data", {}).get("Data", [])

    if not data:

        raise RuntimeError(
            "CryptoCompare veri döndürmedi."
        )

    df = pd.DataFrame(data)

    required_columns = [
        "time",
        "open",
        "high",
        "low",
        "close"
    ]

    for column in required_columns:

        if column not in df.columns:

            raise RuntimeError(
                f"Eksik veri sütunu: {column}"
            )

    df["time"] = pd.to_datetime(
        df["time"],
        unit="s",
        utc=True
    )

    for column in [
        "open",
        "high",
        "low",
        "close"
    ]:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=["open", "high", "low", "close"]
    )

    df = df.sort_values("time").reset_index(
        drop=True
    )

    # ======================================
    # AÇILMAMIŞ MUMU ÇIKAR
    # ======================================

    now = pd.Timestamp.now(
        tz="UTC"
    )

    candle_seconds = TIMEFRAMES[
        timeframe
    ]["seconds"]

    candle_duration = pd.Timedelta(
        seconds=candle_seconds
    )

    if len(df) > 0:

        last_candle_start = df.iloc[-1]["time"]

        last_candle_end = (
            last_candle_start
            + candle_duration
        )

        if last_candle_end > now:

            df = df.iloc[:-1].copy()

    if len(df) < 35:

        raise RuntimeError(
            "MACD hesaplamak için yeterli "
            "kapanmış mum yok."
        )

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

    df["macd"] = (
        ema_fast
        - ema_slow
    )

    df["signal"] = df["macd"].ewm(
        span=MACD_SIGNAL,
        adjust=False
    ).mean()

    return df


# ==========================================
# CROSS KONTROLÜ
# ==========================================

def check_cross(df):

    # Son iki KAPANMIŞ mum

    previous = df.iloc[-2]
    current = df.iloc[-1]

    bullish = (
        previous["macd"]
        <= previous["signal"]
        and
        current["macd"]
        > current["signal"]
    )

    bearish = (
        previous["macd"]
        >= previous["signal"]
        and
        current["macd"]
        < current["signal"]
    )

    if bullish:
        return "BULLISH"

    if bearish:
        return "BEARISH"

    return None


# ==========================================
# ANA PROGRAM
# ==========================================

print("=" * 42)
print("MACD TELEGRAM BOT")
print("=" * 42)
print("Veri        : CryptoCompare")
print("Piyasa      : Binance")
print("Coin sayısı : 10")
print("Zamanlar    : 2H / 4H / 12H / 1D")
print("MACD        : 12 / 26 / 9")
print("Sinyal      : Kapanmış mum")
print("Tekrar      : Engelli")
print("=" * 42)

print()
print("MACD kontrolü başladı.")
print("=" * 42)


state_changed = False


for symbol in SYMBOLS:

    for timeframe_name in TIMEFRAMES:

        try:

            df = get_data(
                symbol,
                timeframe_name
            )

            df = calculate_macd(df)

            cross = check_cross(df)

            if cross:

                # Cross'un gerçekleştiği kapanmış mum
                candle_time = (
                    df.iloc[-1]["time"]
                    .isoformat()
                )

                state_key = (
                    f"{symbol}_{timeframe_name}"
                )

                last_alert = state.get(
                    state_key
                )

                current_alert = {
                    "candle": candle_time,
                    "direction": cross
                }

                # ==================================
                # AYNI CROSS DAHA ÖNCE BİLDİRİLDİ Mİ?
                # ==================================

                if last_alert == current_alert:

                    print(
                        f"Tekrar engellendi | "
                        f"{symbol} | "
                        f"{timeframe_name} | "
                        f"{cross}"
                    )

                    continue

                if cross == "BULLISH":

                    emoji = "🟢"
                    direction_text = "YÜKSELİŞ"

                else:

                    emoji = "🔴"
                    direction_text = "DÜŞÜŞ"

                message = (
                    f"{emoji} MACD CROSS\n\n"
                    f"Coin: {symbol}\n"
                    f"Zaman: {timeframe_name}\n"
                    f"Yön: {direction_text}\n\n"
                    f"MACD: "
                    f"{df.iloc[-1]['macd']:.6f}\n"
                    f"Signal: "
                    f"{df.iloc[-1]['signal']:.6f}"
                )

                # Önce Telegram gönder
                sent = send_telegram(
                    message
                )

                # Telegram başarılıysa state kaydet
                if sent:

                    state[state_key] = (
                        current_alert
                    )

                    state_changed = True

                    print(
                        f"{emoji} "
                        f"{symbol} "
                        f"{timeframe_name} "
                        f"{cross} "
                        f"→ TELEGRAM GÖNDERİLDİ"
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


print("=" * 42)
print("MACD kontrolü tamamlandı.")
print("=" * 42)

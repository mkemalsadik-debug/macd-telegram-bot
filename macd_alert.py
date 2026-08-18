import os
import requests
import pandas as pd
import json

# ==========================================
# AYARLAR
# ==========================================

SYMBOLS = [
    "BTC-USDT",
    "ETH-USDT",
    "BNB-USDT",
    "SOL-USDT",
    "XRP-USDT",
    "DOGE-USDT",
    "ETHFI-USDT",
    "AVAX-USDT",
    "HYPE-USDT",
    "LIT-USDT"
]

TIMEFRAMES = {
    "2H": "2H",
    "4H": "4H",
    "12H": "12H",
    "1D": "1D"
}

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1921028034"

OKX_URL = "https://www.okx.com/api/v5/market/candles"

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

    with open(STATE_FILE, "w", encoding="utf-8") as f:
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
        return

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
        timeout=15
    )

    response.raise_for_status()


# ==========================================
# OKX VERİSİ
# ==========================================

def get_data(symbol, timeframe):

    params = {
        "instId": symbol,
        "bar": timeframe,
        "limit": "100"
    }

    response = requests.get(
        OKX_URL,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    result = response.json()

    if result.get("code") != "0":
        raise Exception(
            f"OKX API: {result.get('msg')}"
        )

    data = result.get("data", [])

    if not data:
        raise Exception("Veri gelmedi.")

    rows = []

    for candle in data:

        # OKX:
        # 0 timestamp
        # 1 open
        # 2 high
        # 3 low
        # 4 close
        # 8 confirm

        rows.append({
            "timestamp": int(candle[0]),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "confirm": candle[8]
        })

    df = pd.DataFrame(rows)

    # OKX en yeni mumu önce döndürür.
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Sadece kapanmış mumlar
    df = df[df["confirm"] == "1"].reset_index(drop=True)

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
# CROSS
# ==========================================

def check_cross(df):

    if len(df) < 3:
        return None

    previous = df.iloc[-2]
    current = df.iloc[-1]

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
print("MACD TELEGRAM BOT")
print("==========================================")
print("Veri        : OKX Public Market Data")
print("Coin sayısı : 10")
print("Zamanlar    : 2H / 4H / 12H / 1D")
print("MACD        : 12 / 26 / 9")
print("Sinyal      : Kapanmış mum")
print("Tekrar      : Engelli")
print("==========================================")
print()
print("MACD kontrolü başladı.")
print("==========================================")


state_changed = False


for symbol in SYMBOLS:

    for timeframe_name, timeframe in TIMEFRAMES.items():

        try:

            df = get_data(
                symbol,
                timeframe
            )

            df = calculate_macd(df)

            cross = check_cross(df)

            state_key = (
                f"{symbol}_{timeframe_name}"
            )

            if cross:

                candle_timestamp = int(
                    df.iloc[-1]["timestamp"]
                )

                signal_key = (
                    f"{candle_timestamp}_{cross}"
                )

                # Aynı kapanmış mumdaki aynı
                # cross daha önce gönderildiyse gönderme.
                if state.get(state_key) == signal_key:

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
                        f"{df.iloc[-1]['macd']:.6f}\n"
                        f"Signal: "
                        f"{df.iloc[-1]['signal']:.6f}"
                    )

                    send_telegram(message)

                    state[state_key] = signal_key
                    state_changed = True

                    print(
                        f"{emoji} "
                        f"{symbol} "
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

    print("==========================================")
    print("State güncellendi.")
    print("==========================================")

else:

    print("==========================================")
    print("State değişmedi.")
    print("==========================================")


print("MACD kontrolü tamamlandı.")
print("==========================================")

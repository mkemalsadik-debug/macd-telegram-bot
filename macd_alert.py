import os
import time
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

CHECK_INTERVAL = 30

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1921028034"

BINANCE_URL = "https://fapi.binance.com/fapi/v1/klines"

# Bağlantı alarm eşikleri
FAIL_THRESHOLD = 3
RECOVER_THRESHOLD = 3


# ==========================================
# TELEGRAM
# ==========================================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=10
        )
    except Exception as e:
        print("Telegram HATASI:", e)


# ==========================================
# BINANCE FUTURES VERİSİ
# ==========================================

def get_data(symbol, interval):

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": 100
    }

    r = requests.get(
        BINANCE_URL,
        params=params,
        timeout=10
    )

    r.raise_for_status()

    data = r.json()

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

    df["open_time"] = pd.to_datetime(
        df["open_time"],
        unit="ms"
    )

    df["close_time"] = pd.to_datetime(
        df["close_time"],
        unit="ms"
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
# CROSS KONTROLÜ
# ==========================================

def get_cross(previous, current):

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
# BAĞLANTI DURUMU
# ==========================================

connection_failures = 0
connection_successes = 0
connection_is_down = False


def report_connection_failure():

    global connection_failures
    global connection_successes
    global connection_is_down

    connection_failures += 1
    connection_successes = 0

    if (
        connection_failures >= FAIL_THRESHOLD
        and
        not connection_is_down
    ):

        send_telegram(
            "🔴 BTC MACD BOT\n\n"
            "Binance Futures bağlantısı kesildi.\n"
            "⚠️ Sinyal kontrolü geçici olarak yapılamıyor."
        )

        connection_is_down = True

        print()
        print("🔴 Binance bağlantısı kesildi!")


def report_connection_success():

    global connection_failures
    global connection_successes
    global connection_is_down

    connection_failures = 0

    if connection_is_down:

        connection_successes += 1

        if connection_successes >= RECOVER_THRESHOLD:

            send_telegram(
                "🟢 BTC MACD BOT\n\n"
                "Binance Futures bağlantısı yeniden sağlandı.\n"
                "✅ Sinyal takibi devam ediyor."
            )

            connection_is_down = False
            connection_successes = 0

            print()
            print("🟢 Binance bağlantısı yeniden sağlandı.")


# ==========================================
# BAŞLANGIÇ
# ==========================================

print()
print("==========================================")
print("       BTC MACD TELEGRAM BOT")
print("==========================================")
print("Coin sayisi :", len(SYMBOLS))
print("Coinler     :", ", ".join(SYMBOLS))
print("Zamanlar    : 2H / 4H / 12H / 1D")
print("MACD        : 12 / 26 / 9")
print("Kontrol     :", CHECK_INTERVAL, "saniye")
print("Veri        : Binance Futures")
print()
print("🟡 Erken cross")
print("🟢 Kapanış onayı")
print("🔴 Bağlantı takibi")
print("==========================================")
print()


# ==========================================
# HAFIZA
# ==========================================

state = {}

for symbol in SYMBOLS:

    state[symbol] = {}

    for name in TIMEFRAMES:

        state[symbol][name] = {
            "live_candle_time": None,
            "live_alert_sent": False,

            "last_closed_candle_time": None,
            "closed_signal_checked": False
        }


# ==========================================
# BAŞLANGIÇ REFERANSINI OLUŞTUR
# ==========================================

print("Başlangıç verileri kontrol ediliyor...")

for symbol in SYMBOLS:

    for name, interval in TIMEFRAMES.items():

        try:

            df = calculate_macd(
                get_data(symbol, interval)
            )

            live_candle = df.iloc[-1]
            closed_candle = df.iloc[-2]

            # ==================================
            # ÇOK ÖNEMLİ:
            #
            # Bot çalışmaya başladığında mevcut
            # canlı mum zaten takip edilmiş kabul edilir.
            #
            # Aynı şekilde mevcut son kapanmış mum
            # da geçmiş kabul edilir.
            #
            # Böylece eski cross bildirilmez.
            # ==================================

            state[symbol][name]["live_candle_time"] = (
                live_candle["open_time"]
            )

            state[symbol][name]["live_alert_sent"] = True

            state[symbol][name]["last_closed_candle_time"] = (
                closed_candle["open_time"]
            )

            state[symbol][name]["closed_signal_checked"] = True

            report_connection_success()

        except Exception as e:

            print(
                f"[BAŞLANGIÇ {symbol} {name}] HATA:",
                e
            )

            report_connection_failure()


print("Başlangıç kontrolü tamamlandı.")
print("Yeni cross'lar bekleniyor...")
print()


# ==========================================
# ANA DÖNGÜ
# ==========================================

while True:

    for symbol in SYMBOLS:

        for name, interval in TIMEFRAMES.items():

            try:

                df = calculate_macd(
                    get_data(symbol, interval)
                )

                live_candle = df.iloc[-1]
                closed_candle = df.iloc[-2]
                previous_closed = df.iloc[-3]

                live_time = live_candle["open_time"]
                closed_time = closed_candle["open_time"]

                current_state = state[symbol][name]


                # ==================================
                # 1️⃣ YENİ CANLI MUM
                # ==================================

                if (
                    current_state["live_candle_time"]
                    != live_time
                ):

                    current_state["live_candle_time"] = live_time

                    # Yeni mum başladı.
                    # Bu mumda henüz erken alarm verilmedi.
                    current_state["live_alert_sent"] = False


                # ==================================
                # 2️⃣ ERKEN CROSS
                # ==================================

                live_cross = get_cross(
                    closed_candle,
                    live_candle
                )

                if (
                    live_cross is not None
                    and
                    not current_state["live_alert_sent"]
                ):

                    if live_cross == "BULLISH":

                        message = (
                            f"🟡 {symbol} {name}\n\n"
                            f"ERKEN YUKARI CROSS\n"
                            f"⚠️ Mum henuz kapanmadi."
                        )

                    else:

                        message = (
                            f"🟡 {symbol} {name}\n\n"
                            f"ERKEN ASAGI CROSS\n"
                            f"⚠️ Mum henuz kapanmadi."
                        )

                    send_telegram(message)

                    print()
                    print(
                        f"[{symbol} {name}] ERKEN CROSS:",
                        live_time,
                        live_cross
                    )

                    current_state["live_alert_sent"] = True


                # ==================================
                # 3️⃣ YENİ KAPANMIŞ MUM
                # ==================================

                if (
                    current_state["last_closed_candle_time"]
                    != closed_time
                ):

                    # Yeni bir mum gerçekten kapanmış.
                    current_state["last_closed_candle_time"] = (
                        closed_time
                    )

                    current_state["closed_signal_checked"] = False


                # ==================================
                # 4️⃣ KAPANIŞ CROSS KONTROLÜ
                # ==================================

                if not current_state["closed_signal_checked"]:

                    closed_cross = get_cross(
                        previous_closed,
                        closed_candle
                    )

                    if closed_cross is not None:

                        if closed_cross == "BULLISH":

                            message = (
                                f"🟢 {symbol} {name}\n\n"
                                f"YUKARI CROSS ONAYLANDI\n"
                                f"✅ Mum kapandi."
                            )

                        else:

                            message = (
                                f"🟢 {symbol} {name}\n\n"
                                f"ASAGI CROSS ONAYLANDI\n"
                                f"✅ Mum kapandi."
                            )

                        send_telegram(message)

                        print()
                        print(
                            f"[{symbol} {name}] KAPANIS ONAYI:",
                            closed_time,
                            closed_cross
                        )

                    # Bu kapanmış mum bir daha kontrol edilmeyecek.
                    current_state["closed_signal_checked"] = True


                report_connection_success()


            except Exception as e:

                print()
                print(
                    f"[{symbol} {name}] HATA:",
                    e
                )

                report_connection_failure()


    print(
        "Kontrol:",
        pd.Timestamp.now().strftime("%H:%M:%S"),
        end="\r"
    )

    time.sleep(CHECK_INTERVAL)
import pandas as pd
import requests
import time
from datetime import datetime
import numpy as np

# === Настройки ===
INTERVAL = "1m"
LIMIT = 200
SLEEP_TIME = 60  # 1 минута
BINANCE_FUTURES_ENDPOINT = "https://fapi.binance.com"

# Цвета ANSI
def color_text(text, color):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "cyan": "\033[96m",
        "end": "\033[0m"
    }
    return f"{colors[color]}{text}{colors['end']}"

# === Получение списка USDT-M фьючерсов (PERPETUAL) ===
def get_usdt_perpetual_symbols():
    url = f"{BINANCE_FUTURES_ENDPOINT}/fapi/v1/exchangeInfo"
    response = requests.get(url)
    symbols = []
    if response.status_code == 200:
        data = response.json()
        for symbol_info in data["symbols"]:
            if symbol_info["quoteAsset"] == "USDT" and symbol_info["contractType"] == "PERPETUAL":
                symbols.append(symbol_info["symbol"])
    return symbols

# === Получение исторических данных ===
def get_klines(symbol, interval, limit):
    url = f"{BINANCE_FUTURES_ENDPOINT}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col])
        return df
    else:
        return None

# === Индикаторы ===
def range_filter_signal(close, period=20, mult=3):
    """Аналог Range Filter: тренд вверх/вниз"""
    ma = close.rolling(period).mean()
    dev = close.rolling(period).std() * mult
    upper = ma + dev
    lower = ma - dev
    if close.iloc[-1] > upper.iloc[-1]:
        return 1  # BUY
    elif close.iloc[-1] < lower.iloc[-1]:
        return -1 # SELL
    return 0

def rqk_signal(close, length=14):
    """Имитация Rational Quadratic Kernel тренда"""
    diff = close.diff()
    up = diff.clip(lower=0).rolling(length).mean()
    down = (-diff.clip(upper=0)).rolling(length).mean()
    rsi = 100 * up / (up + down)
    if rsi.iloc[-1] > 55:
        return 1
    elif rsi.iloc[-1] < 45:
        return -1
    return 0

def supertrend_signal(df, period=10, mult=3):
    hl2 = (df["high"] + df["low"]) / 2
    atr = (df["high"] - df["low"]).rolling(period).mean()
    upperband = hl2 + mult * atr
    lowerband = hl2 - mult * atr
    close = df["close"]
    if close.iloc[-1] > upperband.iloc[-1]:
        return 1
    elif close.iloc[-1] < lowerband.iloc[-1]:
        return -1
    return 0

def halftrend_signal(close, period=20):
    """Упрощённый HalfTrend"""
    ema_high = close.rolling(period).max()
    ema_low = close.rolling(period).min()
    if close.iloc[-1] > ema_high.iloc[-1]:
        return 1
    elif close.iloc[-1] < ema_low.iloc[-1]:
        return -1
    return 0

def donchian_signal(df, period=20):
    upper = df["high"].rolling(period).max()
    lower = df["low"].rolling(period).min()
    close = df["close"]
    if close.iloc[-1] > upper.iloc[-1]:
        return 1
    elif close.iloc[-1] < lower.iloc[-1]:
        return -1
    return 0

# === Логика сигналов ===
last_signal = {}
signal_timer = {}

def get_signal(symbol, df):
    global last_signal, signal_timer
    if df is None or len(df) < 50:
        return "neutral"

    close = df["close"]

    # Leading + Confirmation
    rf_lead = range_filter_signal(close)
    rf_conf = range_filter_signal(close)
    rqk = rqk_signal(close)
    st = supertrend_signal(df)
    ht = halftrend_signal(close)
    dr = donchian_signal(df)

    indicators = [rf_lead, rf_conf, rqk, st, ht, dr]


# Проверяем условия
    if all(sig == 1 for sig in indicators):
        last_signal[symbol] = "long"
        signal_timer[symbol] = 3
    elif all(sig == -1 for sig in indicators):
        last_signal[symbol] = "short"
        signal_timer[symbol] = 3
    else:
        if signal_timer.get(symbol, 0) > 0:
            signal_timer[symbol] -= 1
        else:
            last_signal[symbol] = "neutral"

    return last_signal.get(symbol, "neutral")

# === Основной цикл ===
def run_scanner():
    print(color_text("Стартуем сканер фьючерсов Binance USDT-M каждые 3 минуты", "cyan"))
    while True:
        print(f"\n=== СКАНИРОВАНИЕ: {datetime.now()} ===")
        symbols = get_usdt_perpetual_symbols()
        print(f"Найдено {len(symbols)} рынков.")

        for symbol in symbols:
            df = get_klines(symbol, INTERVAL, LIMIT)
            signal = get_signal(symbol, df)
            if signal == "long":
                print(f"{symbol}: {color_text('LONG', 'green')}")
            elif signal == "short":
                print(f"{symbol}: {color_text('SHORT', 'red')}")
            else:
                print(f"{symbol}: neutral")

        print(f"\nЖдем блять  {SLEEP_TIME // 60} минут...\n")
        time.sleep(SLEEP_TIME)

# Запуск
if __name__ == "__main__":
    run_scanner()
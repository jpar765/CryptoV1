# bot/bot.py — FIXED: All imports verified with alpaca-py
import time
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# === SECRETS (Add in Render Environment Variables) ===
API_KEY = "YOUR_ALPACA_KEY"  # Paper: From alpaca.markets/dashboard
API_SECRET = "YOUR_ALPACA_SECRET"
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"  # From @BotFather
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"  # From api.telegram.org/bot<TOKEN>/getUpdates

SYMBOLS = ["SHIB/USD", "PEPE/USD", "SOL/USD"]
TARGET_USD = 333.33  # For $1,000 account

# Clients (paper=True for testing)
data_client = CryptoHistoricalDataClient(API_KEY, API_SECRET)
trading_client = TradingClient(API_KEY, API_SECRET, paper=True)

# Trackers
highest_price = {sym: 0.0 for sym in SYMBOLS}
entry_price = {sym: 0.0 for sym in SYMBOLS}
last_rebalance = None

def send_telegram(msg):
    if "YOUR_TELEGRAM" not in TELEGRAM_TOKEN:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
        except Exception as e:
            print(f"Telegram send failed: {e}")

def get_data_multi_tf(symbol):
    # 10min main chart
    req_10m = CryptoBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(10, TimeFrame.Unit.Minute),
        start=datetime.now() - timedelta(days=30)
    )
    df_10m = data_client.get_crypto_bars(req_10m).df
    if symbol in df_10m.index.get_level_values(0):
        df_10m = df_10m.xs(symbol)
    df_10m = df_10m[['open', 'high', 'low', 'close', 'volume']]

    # HTF for filters (1H, 4H, 1D)
    req_1h = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Hour, start=datetime.now() - timedelta(days=90))
    df_1h = data_client.get_crypto_bars(req_1h).df.xs(symbol)[['close']]

    req_4h = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame(4, TimeFrame.Unit.Hour), start=datetime.now() - timedelta(days=180))
    df_4h = data_client.get_crypto_bars(req_4h).df.xs(symbol)[['close', 'high', 'low']]

    req_1d = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=datetime.now() - timedelta(days=365))
    df_1d = data_client.get_crypto_bars(req_1d).df.xs(symbol)[['high', 'low']]

    return df_10m, df_1h, df_4h, df_1d

def add_indicators(df_10m, df_1h, df_4h, df_1d):
    close = df_10m['close']
    high = df_10m['high']
    low = df_10m['low']

    # MAs
    for period in [14, 49, 63, 105, 203]:
        df_10m[f'MA_{period}'] = close.rolling(window=period).mean()

    # MACD (7,63,14)
    exp1 = close.ewm(span=7, adjust=False).mean()
    exp2 = close.ewm(span=63, adjust=False).mean()
    df_10m['MACD'] = exp1 - exp2
    df_10m['MACD_Signal'] = df_10m['MACD'].ewm(span=14, adjust=False).mean()
    df_10m['MACD_Hist'] = df_10m['MACD'] - df_10m['MACD_Signal']

    # RSI(10)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=10).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=10).mean()
    rs = gain / loss
    df_10m['RSI_10'] = 100 - (100 / (1 + rs))

    # TTM Squeeze (simplified 10-period)
    df_10m['20sma'] = close.rolling(window=20).mean()
    bb_upper = df_10m['20sma'] + 2 * close.rolling(20).std()
    bb_lower = df_10m['20sma'] - 2 * close.rolling(20).std()
    kc_upper = df_10m['20sma'] + 1.5 * close.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())))
    kc_lower = df_10m['20sma'] - 1.5 * close.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())))
    df_10m['TTM_Squeeze'] = ((bb_upper < kc_upper) & (bb_lower > kc_lower)).astype(int)

    # HTF Filters
    df_1h_res = df_1h['close'].reindex(df_10m.index, method='ffill')
    ma105_1h = df_1h_res.rolling(105).mean()
    df_10m['HTF_Trend'] = (close > ma105_1h).astype(int)

    df_4h_close = df_4h['close'].reindex(df_10m.index, method='ffill')
    exp1_4h = df_4h_close.ewm(span=7).mean()
    exp2_4h = df_4h_close.ewm(span=63).mean()
    macd_4h = exp1_4h - exp2_4h
    df_10m['MACD_Hist_4H'] = (macd_4h - macd_4h.ewm(span=14).mean()).reindex(df_10m.index, method='ffill')

    five_day_high = df_1d['high'].rolling(5).max().reindex(df_10m.index, method='ffill')
    df_10m['5D_High'] = five_day_high
    df_10m['5D_Low'] = df_1d['low'].rolling(5).min().reindex(df_10m.index, method='ffill')

    return df_10m

def get_position_qty(symbol):
    try:
        pos = trading_client.get_position(symbol)
        return float(pos.qty)
    except:
        return 0.0

def buy_coin(symbol, usd_amount):
    df_10m, _, _, _ = get_data_multi_tf(symbol)
    price = df_10m['close'].iloc[-1]
    qty = round(usd_amount / price, 8)
    if qty > 0:
        order = MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
        trading_client.submit_order(order)
        print(f"BUY {qty:.2f} {symbol} @ ${price:.6f}")

def sell_all(symbol):
    qty = get_position_qty(symbol)
    if qty > 0:
        trading_client.close_position(symbol)
        print(f"SELL ALL {symbol}")

def generate_signals(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    buy = (
        (latest['close'] > latest['MA_14']) &
        (latest['MACD'] > latest['MACD_Signal']) &
        (latest['MACD_Hist'] > prev['MACD_Hist']) &
        (30 < latest['RSI_10'] < 65) &
        (latest['TTM_Squeeze'] == 0) &
        (latest['HTF_Trend'] == 1) &
        (latest['MACD_Hist_4H'] > 0) &
        (latest['close'] > latest['5D_Low']) &
        (latest['close'] > latest['5D_High'].shift(20).iloc[-1])
    )
    sell = (latest['RSI_10'] > 78) | (latest['close'] < latest['MA_63'])
    return buy, sell

def daily_rebalance():
    global last_rebalance
    today = datetime.now(timezone.utc).date()
    if last_rebalance != today:
        print("DAILY REBALANCE — Flattening positions...")
        send_telegram("Daily Rebalance: Closing all positions...")
        for sym in SYMBOLS:
            sell_all(sym)
        time.sleep(10)
        send_telegram("Re-allocating $333 to each coin...")
        for sym in SYMBOLS:
            buy_coin(sym, TARGET_USD)
            time.sleep(3)
        last_rebalance = today
        send_telegram("Rebalance complete!")

def main():
    print("SHIB/PEPE/SOL 24/7 Bot Started | $1,000 Paper Account")
    send_telegram("🚀 Bot launched successfully!")
    while True:
        try:
            # Daily rebalance check
            now_utc = datetime.now(timezone.utc)
            if now_utc.hour == 0 and now_utc.minute < 5:
                daily_rebalance()

            for symbol in SYMBOLS:
                df_10m, df_1h, df_4h, df_1d = get_data_multi_tf(symbol)
                df = add_indicators(df_10m, df_1h, df_4h, df_1d)
                latest = df.iloc[-1]
                current_qty = get_position_qty(symbol)
                buy_sig, sell_sig = generate_signals(df)

                # Entry
                if buy_sig and current_qty == 0:
                    buy_coin(symbol, TARGET_USD)
                    time.sleep(3)  # Wait for fill
                    try:
                        pos = trading_client.get_position(symbol)
                        entry_price[symbol] = float(pos.avg_entry_price)
                        highest_price[symbol] = entry_price[symbol]
                    except:
                        entry_price[symbol] = latest['close']
                        highest_price[symbol] = latest['close']
                    send_telegram(f"🟢 BUY {symbol} @ ${latest['close']:.6f}")

                # Exit Management
                if current_qty > 0:
                    pos = trading_client.get_position(symbol)
                    entry_p = float(pos.avg_entry_price)
                    current_p = latest['close']
                    profit_pct = (current_p - entry_p) / entry_p

                    # Update peak
                    if current_p > highest_price[symbol]:
                        highest_price[symbol] = current_p

                    peak = highest_price[symbol]
                    trail_trigger = peak * 0.97  # 3%

                    # TP 6%
                    if current_p >= entry_p * 1.06:
                        sell_all(symbol)
                        msg = f"💰 TP +6% {symbol} @ ${current_p:.6f}"
                        send_telegram(msg)
                        print(msg)
                        highest_price[symbol] = entry_price[symbol] = 0.0

                    # Trailing 3%
                    elif peak > entry_p * 1.005 and current_p <= trail_trigger:
                        sell_all(symbol)
                        msg = f"📉 Trailing Stop {symbol} @ ${current_p:.6f} (+{profit_pct*100:.2f}%)"
                        send_telegram(msg)
                        print(msg)
                        highest_price[symbol] = entry_price[symbol] = 0.0

                    # SL 1.5%
                    elif current_p <= entry_p * 0.985:
                        sell_all(symbol)
                        msg = f"🛑 SL -1.5% {symbol} @ ${current_p:.6f}"
                        send_telegram(msg)
                        print(msg)
                        highest_price[symbol] = entry_price[symbol] = 0.0

                    # Signal Sell
                    elif sell_sig:
                        sell_all(symbol)
                        msg = f"🔴 Signal Exit {symbol} (+{profit_pct*100:.2f}%)"
                        send_telegram(msg)
                        print(msg)
                        highest_price[symbol] = entry_price[symbol] = 0.0

            # Heartbeat every 10 min
            if int(time.time()) % 600 == 0:
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Bot running | Positions checked")

            time.sleep(60)  # Check every minute

        except Exception as e:
            error_msg = f"Bot Error: {e}"
            print(error_msg)
            send_telegram(error_msg)
            time.sleep(60)

if __name__ == "__main__":
    main()
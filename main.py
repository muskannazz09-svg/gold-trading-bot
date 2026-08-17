import os
import time
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Render Environment Variables se API keys set honge
API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')

# Binance Testnet Client Initialization
client = Client(API_KEY, API_SECRET, testnet=True)

SYMBOL = 'XAUUSDT'  # Gold Perpetual Futures
QUANTITY = 0.01     # Risk Lot Size (Min Lot Size)
TIMEFRAME = '5m'    # 5-Minute timeframe

def fetch_klines():
    """Fetch recent price candles"""
    klines = client.futures_klines(symbol=SYMBOL, interval=TIMEFRAME, limit=100)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
    ])
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    return df

def calculate_indicators(df):
    """Trend, Momentum & Risk Indicators (EMA 200, RSI 14, ATR 14)"""
    # 1. EMA 200 (Trend Filter)
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # 2. RSI 14 (Momentum Filter)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 3. ATR 14 (Volatilitiy & Dynamic Risk Management)
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = abs(df['high'] - df['close'].shift(1))
    df['tr3'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    return df

def check_trade_signal(df):
    """Smart Entry Logic: Trend Following + Reversals"""
    latest = df.iloc[-1]
    price = latest['close']
    ema = latest['EMA_200']
    rsi = latest['RSI']
    atr = latest['ATR']
    
    # Uptrend + Oversold Pullback = LONG / BUY
    if price > ema and rsi < 35:
        return 'BUY', price, atr
        
    # Downtrend + Overbought Pullback = SHORT / SELL
    elif price < ema and rsi > 65:
        return 'SELL', price, atr
        
    return None, price, atr

def execute_smart_trade(side, entry_price, atr):
    """Execute Trade with Auto Take-Profit & Stop-Loss (1:2 Risk-Reward)"""
    try:
        # Dynamic Risk Calculation based on ATR
        sl_distance = max(atr * 1.5, 1.5)  # Minimum $1.5 SL
        tp_distance = sl_distance * 2.0    # 1:2 Risk to Reward Ratio
        
        if side == 'BUY':
            tp_price = round(entry_price + tp_distance, 2)
            sl_price = round(entry_price - sl_distance, 2)
            close_side = 'SELL'
        else:
            tp_price = round(entry_price - tp_distance, 2)
            sl_price = round(entry_price + sl_distance, 2)
            close_side = 'BUY'

        # 1. Main Market Order
        order = client.futures_create_order(
            symbol=SYMBOL, side=side, type='MARKET', quantity=QUANTITY
        )
        print(f"\n[ENTRY EXECUTED] {side} @ ${entry_price:.2f}")

        # 2. Automated Take-Profit
        client.futures_create_order(
            symbol=SYMBOL, side=close_side, type='TAKE_PROFIT_MARKET',
            stopPrice=tp_price, closePosition=True
        )

        # 3. Automated Stop-Loss
        client.futures_create_order(
            symbol=SYMBOL, side=close_side, type='STOP_MARKET',
            stopPrice=sl_price, closePosition=True
        )

        print(f"[RISK MANAGED] TP Target: ${tp_price} | SL Limit: ${sl_price}\n")

    except BinanceAPIException as e:
        print(f"[API ERROR] Order execution failed: {e.message}")
    except Exception as e:
        print(f"[ERROR] {e}")

# ==========================================
# MAIN CLOUD EXECUTION LOOP
# ==========================================
print("==================================================")
print("Gold Trading Bot Running 24/7 on Cloud...")
print("==================================================")

while True:
    try:
        # Step 1: Check Open Positions
        positions = client.futures_position_information(symbol=SYMBOL)
        position_amt = float(positions[0]['positionAmt'])

        if position_amt == 0:
            df = fetch_klines()
            df = calculate_indicators(df)
            signal, price, atr = check_trade_signal(df)
            
            t_stamp = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{t_stamp}] Gold Price: ${price:.2f} | RSI: {df.iloc[-1]['RSI']:.1f} | Scanning...")

            if signal:
                print(f"\n>>> CRITERIA MATCHED: {signal} SIGNAL GENERATED <<<")
                execute_smart_trade(signal, price, atr)
        else:
            t_stamp = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{t_stamp}] Active Trade in progress (Size: {position_amt}). Waiting for TP/SL...")

        time.sleep(60)

    except Exception as e:
        print(f"[CLOUD ENGINE ERROR] {e}. Retrying in 15s...")
        time.sleep(15)

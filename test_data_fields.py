#!/usr/bin/env python
"""
Quick test to verify what fields are included in downloaded market data
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

print("Testing Market Data Fields with New P/E Ratios")
print("=" * 60)

# Test with AAPL
ticker = 'AAPL'
print(f"\nFetching data for {ticker}...")

ticker_obj = yf.Ticker(ticker)

# Get historical data (last 5 days)
end_date = datetime.now()
start_date = end_date - timedelta(days=5)
ohlc_data = ticker_obj.history(start=start_date, end=end_date, interval='1d')

# Get additional info
info = ticker_obj.info

# Fields that will be added to each row
additional_params = [
    'volume', 'averageDailyVolume10Day', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow',
    'fiftyDayAverage', 'twoHundredDayAverage', 'marketCap', 'industry', 'sector', 'exchange',
    'trailingPE', 'forwardPE'  # NEW P/E ratio metrics
]

# Add them to the dataframe
for param in additional_params:
    if param in info:
        ohlc_data[param] = info[param]
    else:
        ohlc_data[param] = 'N/A'

ohlc_data['Symbol'] = ticker

print(f"\n✅ Data fetched successfully!")
print(f"   Rows: {len(ohlc_data)}")
print(f"   Columns: {len(ohlc_data.columns)}")

print(f"\n📊 Available Columns:")
print("-" * 60)
for i, col in enumerate(ohlc_data.columns, 1):
    print(f"{i:2d}. {col}")

print(f"\n📈 Sample Data (Latest Row):")
print("-" * 60)
if len(ohlc_data) > 0:
    latest = ohlc_data.iloc[-1]

    # OHLCV Data
    print("\n🔹 OHLCV Data:")
    print(f"   Date: {ohlc_data.index[-1]}")
    print(f"   Open: ${latest['Open']:.2f}")
    print(f"   High: ${latest['High']:.2f}")
    print(f"   Low: ${latest['Low']:.2f}")
    print(f"   Close: ${latest['Close']:.2f}")
    print(f"   Volume: {latest['Volume']:,}")

    # P/E Ratios (NEW!)
    print("\n🔹 P/E Ratios (NEW!):")
    print(f"   Trailing P/E: {latest['trailingPE']}")
    print(f"   Forward P/E: {latest['forwardPE']}")

    # 52-Week Range
    print("\n🔹 52-Week Range:")
    print(f"   52-Week High: ${latest['fiftyTwoWeekHigh']:.2f}")
    print(f"   52-Week Low: ${latest['fiftyTwoWeekLow']:.2f}")

    # Moving Averages
    print("\n🔹 Moving Averages:")
    print(f"   50-Day MA: ${latest['fiftyDayAverage']:.2f}")
    print(f"   200-Day MA: ${latest['twoHundredDayAverage']:.2f}")

    # Company Info
    print("\n🔹 Company Info:")
    print(f"   Symbol: {latest['Symbol']}")
    print(f"   Market Cap: ${latest['marketCap']:,}")
    print(f"   Sector: {latest['sector']}")
    print(f"   Industry: {latest['industry']}")
    print(f"   Exchange: {latest['exchange']}")
    print(f"   Avg Volume (10d): {latest['averageDailyVolume10Day']:,}")

print("\n" + "=" * 60)
print("✅ All fields verified!")
print("\nThese fields will be included in every downloaded CSV file.")
print("Each row will have the same fundamental data repeated")
print("(since they're stock-level attributes, not date-specific).")
print("\nNote: P/E ratios and other fundamentals are point-in-time")
print("values at the time of download, not historical values.")
print("=" * 60)

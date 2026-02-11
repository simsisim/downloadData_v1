# TradingView Column Mapping Reference

## Exact Column Mapping: TW Bulk File → Ticker CSV

---

## **TradingView Bulk File Columns (Input)**

Your TW file has these columns:
```
Symbol
Description
Market capitalization
Market capitalization - Currency
Sector
Industry
Exchange
Analyst Rating
Upcoming earnings date
Recent earnings date
Index
High 1 day
High 1 day - Currency
Low 1 day
Low 1 day - Currency
Open 1 day
Open 1 day - Currency
Price
Price - Currency
Volume 1 day
```

**Total**: 20 columns

---

## **Target Ticker CSV Format (Output)**

Your individual ticker files should have:
```
Date
Open
High
Low
Close
Volume
```

**Total**: 6 columns

---

## **Column Extraction Mapping**

| TW Column Name | Use? | → | Ticker CSV Column | Notes |
|----------------|------|---|-------------------|-------|
| **Symbol** | ✅ | → | (ticker filename) | Used for `AAPL.csv` filename |
| Description | ❌ | | (ignore) | Not needed for OHLCV |
| Market capitalization | ❌ | | (ignore) | Metadata, not price data |
| Market capitalization - Currency | ❌ | | (ignore) | Not needed |
| Sector | ❌ | | (ignore) | Already in your metadata |
| Industry | ❌ | | (ignore) | Already in your metadata |
| Exchange | ❌ | | (ignore) | Already in your metadata |
| Analyst Rating | ❌ | | (ignore) | Not needed |
| Upcoming earnings date | ❌ | | (ignore) | Not needed |
| Recent earnings date | ❌ | | (ignore) | Not needed |
| Index | ❌ | | (ignore) | Not needed |
| **High 1 day** | ✅ | → | **High** | ⚠️ Use this, not "High 1 day - Currency" |
| High 1 day - Currency | ❌ | | (ignore) | Currency label, not data |
| **Low 1 day** | ✅ | → | **Low** | ⚠️ Use this, not "Low 1 day - Currency" |
| Low 1 day - Currency | ❌ | | (ignore) | Currency label, not data |
| **Open 1 day** | ✅ | → | **Open** | ⚠️ Use this, not "Open 1 day - Currency" |
| Open 1 day - Currency | ❌ | | (ignore) | Currency label, not data |
| **Price** | ✅ | → | **Close** | ⚠️ TW uses "Price" for Close price |
| Price - Currency | ❌ | | (ignore) | Currency label, not data |
| **Volume 1 day** | ✅ | → | **Volume** | Direct mapping |
| (filename date) | ✅ | → | **Date** | Extract from filename |

---

## **Python Implementation**

### **Exact Column Names for pandas:**

```python
# Columns to extract from TW file
TW_COLUMNS = {
    'ticker': 'Symbol',              # For identification
    'Open': 'Open 1 day',            # ⚠️ Note the space
    'High': 'High 1 day',            # ⚠️ Note the space
    'Low': 'Low 1 day',              # ⚠️ Note the space
    'Close': 'Price',                # ⚠️ TW uses "Price"
    'Volume': 'Volume 1 day'         # ⚠️ Note the space
}

# Columns to IGNORE (do not extract)
IGNORE_COLUMNS = [
    'Description',
    'Market capitalization',
    'Market capitalization - Currency',
    'Sector',
    'Industry',
    'Exchange',
    'Analyst Rating',
    'Upcoming earnings date',
    'Recent earnings date',
    'Index',
    'High 1 day - Currency',
    'Low 1 day - Currency',
    'Open 1 day - Currency',
    'Price - Currency'
]
```

### **Extraction Function:**

```python
def extract_ohlcv_from_tw_row(row, date):
    """
    Extract OHLCV data from a TradingView bulk file row

    Args:
        row: pandas Series (one row from TW file)
        date: datetime.date (extracted from filename)

    Returns:
        dict: {'Date': date, 'Open': ..., 'High': ..., 'Low': ..., 'Close': ..., 'Volume': ...}
    """
    return {
        'Date': date,
        'Open': row['Open 1 day'],      # ⚠️ Column name with space
        'High': row['High 1 day'],      # ⚠️ Column name with space
        'Low': row['Low 1 day'],        # ⚠️ Column name with space
        'Close': row['Price'],          # ⚠️ "Price" → "Close"
        'Volume': row['Volume 1 day']   # ⚠️ Column name with space
    }
```

### **Full Parsing Example:**

```python
def parse_tw_bulk_file(filepath, file_date):
    """
    Parse TradingView bulk CSV file

    Args:
        filepath: Path to TW bulk CSV
        file_date: Date extracted from filename (datetime.date)

    Returns:
        dict: {ticker: {Date, Open, High, Low, Close, Volume}}
    """
    # Read TW file
    df = pd.read_csv(filepath)

    ticker_data = {}

    for idx, row in df.iterrows():
        # Get ticker symbol
        ticker = row['Symbol']

        if pd.isna(ticker):
            continue

        # Clean ticker
        ticker = str(ticker).strip()
        ticker = ticker.replace('.', '-')  # BRK.A → BRK-A

        # Skip tickers with slashes (preferred shares)
        if '/' in ticker:
            continue

        # Extract OHLCV data
        try:
            ticker_data[ticker] = {
                'Date': file_date,
                'Open': row['Open 1 day'],      # ⚠️ Exact column name
                'High': row['High 1 day'],      # ⚠️ Exact column name
                'Low': row['Low 1 day'],        # ⚠️ Exact column name
                'Close': row['Price'],          # ⚠️ Price → Close
                'Volume': row['Volume 1 day']   # ⚠️ Exact column name
            }
        except KeyError as e:
            print(f"⚠️ Missing column for {ticker}: {e}")
            continue

    return ticker_data
```

---

## **Example Transformation**

### **Input (TW bulk file row):**
```csv
Symbol: AAPL
Description: Apple Inc.
Market capitalization: 3354078740480
Market capitalization - Currency: USD
Sector: Technology
Industry: Consumer Electronics
Exchange: NMS
Analyst Rating: Buy
Upcoming earnings date: 2025-11-01
Recent earnings date: 2025-08-01
Index: NASDAQ 100, S&P 500
High 1 day: 186.86
High 1 day - Currency: USD
Low 1 day: 182.35
Low 1 day - Currency: USD
Open 1 day: 185.58
Open 1 day - Currency: USD
Price: 184.08
Price - Currency: USD
Volume 1 day: 82488700

Filename: all_stocks _OHLCV_2025-10-01.csv
```

### **Output (AAPL.csv - new row):**
```csv
Date,Open,High,Low,Close,Volume
2025-10-01,185.58,186.86,182.35,184.08,82488700
```

### **What We Extracted:**
- ✅ Symbol → Used for filename: `AAPL.csv`
- ✅ Open 1 day: `185.58` → Open
- ✅ High 1 day: `186.86` → High
- ✅ Low 1 day: `182.35` → Low
- ✅ Price: `184.08` → Close
- ✅ Volume 1 day: `82488700` → Volume
- ✅ Filename date: `2025-10-01` → Date

### **What We Ignored:**
- ❌ All metadata columns (Description, Market cap, Sector, etc.)
- ❌ All currency labels (High 1 day - Currency, etc.)
- ❌ All dates columns (Earnings dates)
- ❌ Index information

---

## **Column Name Validation**

### **Before Processing, Validate TW File:**

```python
def validate_tw_file_columns(filepath):
    """
    Validate that TW file has all required columns

    Args:
        filepath: Path to TW bulk CSV

    Returns:
        bool: True if valid, False otherwise
    """
    df = pd.read_csv(filepath, nrows=0)  # Read only header

    required_columns = [
        'Symbol',
        'Open 1 day',
        'High 1 day',
        'Low 1 day',
        'Price',
        'Volume 1 day'
    ]

    missing_columns = []
    for col in required_columns:
        if col not in df.columns:
            missing_columns.append(col)

    if missing_columns:
        print(f"❌ Missing required columns: {missing_columns}")
        print(f"   Available columns: {list(df.columns)}")
        return False

    print(f"✅ TW file has all required columns")
    return True
```

---

## **Common Issues & Solutions**

### **Issue 1: Column name has extra spaces**
```python
# Problem: "Open 1 day " (trailing space)
# Solution: Strip column names when reading
df = pd.read_csv(filepath)
df.columns = df.columns.str.strip()
```

### **Issue 2: Column names are case-sensitive**
```python
# TW file has: "open 1 day" (lowercase)
# Expected: "Open 1 day" (capitalized)
# Solution: Make matching case-insensitive

# Create column mapping
column_lower = {col.lower(): col for col in df.columns}

# Access with case-insensitive lookup
open_col = column_lower.get('open 1 day')
df[open_col]  # Works regardless of case
```

### **Issue 3: NaN or missing values**
```python
# Check for NaN values before extraction
if pd.isna(row['Open 1 day']) or pd.isna(row['Price']):
    print(f"⚠️ {ticker}: Missing OHLCV data, skipping")
    continue
```

### **Issue 4: Volume is string (e.g., "82,488,700")**
```python
# Solution: Clean and convert to numeric
volume = row['Volume 1 day']
if isinstance(volume, str):
    volume = volume.replace(',', '')
    volume = float(volume)
```

---

## **Output Format Specification**

### **Ticker CSV File Format:**
```csv
Date,Open,High,Low,Close,Volume
2024-01-02,185.58,186.86,182.35,184.08,82488700
2024-01-03,182.67,184.32,181.89,182.70,58414500
2025-10-01,185.58,186.86,182.35,184.08,82488700
```

### **Format Requirements:**
- **Date**: YYYY-MM-DD format (e.g., `2025-10-01`)
- **Open**: Float, 2 decimal places recommended
- **High**: Float, 2 decimal places recommended
- **Low**: Float, 2 decimal places recommended
- **Close**: Float, 2 decimal places recommended
- **Volume**: Integer (no decimals)

### **Column Order:**
Must be exactly: `Date, Open, High, Low, Close, Volume`

**NOT** `Date, Low, Open, High, Close, Volume` (LOHCV)

---

## **Summary**

### **Simple Rule:**
From TW file's 20 columns, we only care about **6**:

1. **Symbol** → ticker (for filename)
2. **Open 1 day** → Open
3. **High 1 day** → High
4. **Low 1 day** → Low
5. **Price** → Close (⚠️ key mapping!)
6. **Volume 1 day** → Volume

Plus: **Date** from filename

**Ignore everything else** (14 columns)

---

## **Quick Reference Table**

| What We Need | TW Column Name | Output Column | Notes |
|--------------|----------------|---------------|-------|
| Ticker | `Symbol` | filename | AAPL.csv |
| Date | (filename) | `Date` | From filename |
| Open | `Open 1 day` | `Open` | Note the space |
| High | `High 1 day` | `High` | Note the space |
| Low | `Low 1 day` | `Low` | Note the space |
| Close | `Price` | `Close` | **Price → Close** |
| Volume | `Volume 1 day` | `Volume` | Note the space |

**Remember**:
- TW uses `Price` for what we call `Close`
- Column names have spaces: `"Open 1 day"` not `"Open1day"`
- Date comes from filename, not from file content

---

**END OF REFERENCE**

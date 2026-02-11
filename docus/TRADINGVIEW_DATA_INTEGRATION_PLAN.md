# TradingView Data Integration Plan

## Document Date: 2025-10-01

---

## 1. PROBLEM STATEMENT

### Current System Limitations
- **Yahoo Finance Download Time**: ~3 hours for 6000 tickers
- **Manual Process**: Historical data from Yahoo Finance requires sequential API calls
- **Update Bottleneck**: Daily updates are time-consuming

### Proposed Solution
- **TradingView Bulk Download**: Single CSV file containing all tickers' data for a given date
- **Faster Updates**: Parse one CSV file and distribute to individual ticker files
- **Additional Capability**: Access to intraday data (future enhancement)

---

## 2. CURRENT SYSTEM ANALYSIS

### Directory Structure
```
/home/imagda/_invest2024/python/downloadData_v1/
├── data/
│   ├── market_data/              # Yahoo Finance data (current system)
│   │   ├── daily/                # Individual ticker CSV files (AAPL.csv, MSFT.csv, etc.)
│   │   ├── weekly/
│   │   └── monthly/
│   ├── market_data_tw/           # TradingView data (historical - already created)
│   │   ├── daily/                # Individual ticker CSV files
│   │   ├── weekly/
│   │   └── monthly/
│   └── tw_files/                 # TradingView bulk download files
│       ├── daily/                # all_stocks _LOHC_2025-10-01.csv
│       ├── weekly/               # all_stocks _LOHC_weekly_2025-XX-XX.csv
│       └── monthly/              # all_stocks _LOHC_monthly_2025-XX.csv
└── src/
    ├── get_marketData.py         # Yahoo Finance data retrieval
    ├── tradingview_ticker_processor.py  # TradingView ticker processing
    └── config.py                 # Configuration management
```

### Data Format Analysis

#### Yahoo Finance Format (AAPL.csv in market_data/daily/):
```csv
Date,Open,High,Low,Close,Volume,Dividends,Stock Splits,volume,averageDailyVolume10Day,...
2024-01-02 00:00:00-05:00,185.58,186.86,182.35,184.08,82488700,0.0,0.0,...
```
- Date is first column with timestamp
- OHLCV + metadata columns
- Each ticker is separate file

#### TradingView Format (all_stocks _LOHC_2025-10-01.csv):
```csv
Symbol,Description,Market capitalization,...,High 1 day,Low 1 day,Open 1 day,Price,Volume 1 day
UPC,Universe Pharmaceuticals Inc,2366019.999,...,4.605,4.2,4.58,4.2,23002
AAPL,Apple Inc.,1084627562115.000,...,186.86,182.35,185.58,184.08,82488700
```
- **All tickers in single file** (~6703 tickers)
- Date is in **filename**, not in content
- Columns: Symbol, LOHC (Low, Open, High, Close/Price), Volume
- **KEY DIFFERENCE**: Need to extract LOHC columns and add date from filename

---

## 3. THREE DATA ROUTES (PARALLEL SYSTEMS)

### Route 1: Yahoo Finance (Current System - Keep Unchanged)
- **Source**: Yahoo Finance API via yfinance
- **Storage**: `data/market_data/{daily,weekly,monthly}/`
- **Update Logic**: Compare latest date in file vs. YF latest date
- **Status**: Production, working, do not modify
- **Flags**:
  - `YF_hist_data` (master)
  - `YF_daily_data`, `YF_weekly_data`, `YF_monthly_data`

### Route 2: TradingView Updates (New System - To Be Implemented)
- **Source**: TradingView bulk CSV files
- **Storage**: `data/market_data_tw/{daily,weekly,monthly}/`
- **Update Logic**: Compare latest date in file vs. latest TW file date (from filename)
- **Status**: To be implemented
- **Flags**:
  - `TW_hist_data` (master)
  - `TW_daily_data`, `TW_weekly_data`, `TW_monthly_data`

### Route 3: Intraday Data (Future Enhancement)
- **Source**: TradingView intraday data
- **Storage**: `data/market_data_intraday/` (not yet created)
- **Status**: Placeholder for future development
- **Use Case**: Not defined yet, no strategy

---

## 4. IMPLEMENTATION LOCATION DECISION

### Option A: Implement in `metaData_v1`
**Pros:**
- Closer to metadata processing
- Separate from main data collection

**Cons:**
- metaData_v1 is about metadata extraction, not market data collection
- Would create architectural confusion
- Different focus area

### Option B: Implement in `downloadData_v1` ✅ **RECOMMENDED**
**Pros:**
- Natural home for market data operations
- Already contains `get_marketData.py` (Yahoo Finance)
- TW data directories already exist here
- Similar update logic can be reused
- Consistent with existing architecture

**Cons:**
- None significant

### **DECISION: Implement in `downloadData_v1`**

---

## 5. MODULE DESIGN

### New Module: `src/get_tradingview_data.py`

#### Class: `TradingViewDataRetriever`

**Responsibilities:**
1. Parse TradingView bulk CSV files from `data/tw_files/{daily,weekly,monthly}/`
2. Extract date from filename (e.g., "all_stocks _LOHC_2025-10-01.csv" → "2025-10-01")
3. Transform TW format to individual ticker CSV files
4. Append new data to existing ticker files in `data/market_data_tw/{timeframe}/`
5. Compare dates to avoid duplicate updates
6. Handle problematic tickers

#### Key Methods:

```python
class TradingViewDataRetriever:
    def __init__(self, config):
        """Initialize with configuration"""

    def find_latest_tw_file(self, timeframe):
        """Find latest TW CSV file in tw_files/{timeframe}/"""
        # Parse filenames, extract dates, return latest

    def extract_date_from_filename(self, filename):
        """Extract date from filename: all_stocks _LOHC_2025-10-01.csv → 2025-10-01"""

    def get_ticker_latest_date(self, ticker, timeframe):
        """Get latest date in ticker's CSV file in market_data_tw/{timeframe}/"""

    def parse_tw_bulk_file(self, filepath, date):
        """Parse TW bulk CSV file and return dict of ticker → OHLCV data"""
        # Extract: Symbol, Open 1 day, High 1 day, Low 1 day, Price, Volume 1 day
        # Rename: Open 1 day → Open, High 1 day → High, etc.
        # Add Date column with extracted date

    def update_ticker_file(self, ticker, new_data, timeframe):
        """Append new data to ticker's CSV file"""
        # Read existing file
        # Append new data
        # Remove duplicates (by date)
        # Sort by date
        # Save

    def update_from_tw_files(self, timeframe):
        """Main update process for a timeframe (daily/weekly/monthly)"""
        # 1. Find latest TW file
        # 2. Extract date from filename
        # 3. For each ticker in universe:
        #    a. Check if ticker's file has this date already
        #    b. If not, parse TW file and extract ticker's data
        #    c. Append to ticker's file
        # 4. Track problematic tickers

    def save_problematic_tickers(self):
        """Save list of problematic tickers"""
```

---

## 6. DATA TRANSFORMATION LOGIC

### TradingView CSV Columns → Standard OHLCV Format

**TradingView columns:**
- `Symbol` → Ticker symbol
- `Open 1 day` → Open
- `High 1 day` → High
- `Low 1 day` → Low
- `Price` → Close
- `Volume 1 day` → Volume

**Output format (matching YF structure):**
```csv
Date,Open,High,Low,Close,Volume
2025-10-01,185.58,186.86,182.35,184.08,82488700
```

**Key Note**: Use **LOHC** order (Low, Open, High, Close) as per user preference, but store in standard OHLCV format for consistency with existing code.

---

## 7. UPDATE LOGIC (SIMILAR TO YAHOO FINANCE)

### Comparison Strategy

```python
def needs_update(ticker, timeframe, tw_file_date):
    """
    Determine if ticker needs update from TW file

    Args:
        ticker: Ticker symbol
        timeframe: daily/weekly/monthly
        tw_file_date: Date extracted from TW filename

    Returns:
        bool: True if update needed
    """
    ticker_file = f"data/market_data_tw/{timeframe}/{ticker}.csv"

    if not os.path.exists(ticker_file):
        return True  # File doesn't exist, needs creation

    # Read ticker file
    df = pd.read_csv(ticker_file, parse_dates=['Date'])

    if df.empty:
        return True

    latest_date_in_file = df['Date'].max().date()

    # If TW file date is newer than latest date in file, update needed
    return tw_file_date > latest_date_in_file
```

---

## 8. CONFIGURATION FLAGS

### New Flags in `user_data.csv`

Add to existing configuration:

```csv
# TRADINGVIEW DATA UPDATES
# ------------------------
TW_hist_data,TRUE,Update historical data from TradingView bulk files
TW_daily_data,TRUE,Process daily TradingView files
TW_weekly_data,TRUE,Process weekly TradingView files
TW_monthly_data,TRUE,Process monthly TradingView files
TW_files_dir,data/tw_files,Directory containing TradingView bulk CSV files
```

### Flag Priority
- If both `YF_hist_data` and `TW_hist_data` are TRUE, both run independently
- If user wants only TW updates, set `YF_hist_data=FALSE` and `TW_hist_data=TRUE`
- Routes are parallel and independent

---

## 9. INTEGRATION WITH MAIN.PY

### Update main.py workflow:

```python
def main():
    # ... existing ticker retrieval logic ...

    # ============ ROUTE 1: YAHOO FINANCE DATA (EXISTING) ============
    if config.yf_hist_data:
        print("Downloading Yahoo Finance historical data...")
        # ... existing YF download logic ...

    # ============ ROUTE 2: TRADINGVIEW DATA (NEW) ============
    if config.tw_hist_data:
        print("\n" + "="*60)
        print("UPDATING DATA FROM TRADINGVIEW BULK FILES")
        print("="*60)

        from src.get_tradingview_data import TradingViewDataRetriever

        tw_retriever = TradingViewDataRetriever(config)

        if config.tw_daily_data:
            print("\n📅 Processing TradingView daily data...")
            tw_retriever.update_from_tw_files('daily')

        if config.tw_weekly_data:
            print("\n📅 Processing TradingView weekly data...")
            tw_retriever.update_from_tw_files('weekly')

        if config.tw_monthly_data:
            print("\n📅 Processing TradingView monthly data...")
            tw_retriever.update_from_tw_files('monthly')

    # ============ ROUTE 3: INTRADAY DATA (FUTURE) ============
    # Placeholder for future implementation
```

---

## 10. ERROR HANDLING & EDGE CASES

### Problematic Scenarios

1. **TW file not found for timeframe**
   - Solution: Log warning, skip that timeframe

2. **Ticker in TW file but not in universe**
   - Solution: Skip ticker, log as info

3. **Ticker in universe but not in TW file**
   - Solution: Add to problematic_tickers list

4. **Date parsing fails from filename**
   - Solution: Raise error, halt processing for that timeframe

5. **Column names don't match expected format**
   - Solution: Use flexible column matching with fallbacks

6. **Multiple TW files for same date**
   - Solution: Use most recent file (by modification time)

### Problematic Tickers File
- Similar to YF: `problematic_tickers_tw_{choice}.csv`
- Store in `data/tickers/`
- Columns: ticker, error, timeframe, date_attempted

---

## 11. DIRECTORY STRUCTURE UPDATES

### Update `config.py`:

```python
PARAMS_DIR = {
    "DATA_DIR": "data",
    "TICKERS_DIR": os.path.join("data", "tickers"),

    # Yahoo Finance routes
    "MARKET_DATA_DIR_1d": os.path.join("data", "market_data/daily/"),
    "MARKET_DATA_DIR_1wk": os.path.join("data", "market_data/weekly/"),
    "MARKET_DATA_DIR_1mo": os.path.join("data", "market_data/monthly/"),

    # TradingView routes (NEW)
    "MARKET_DATA_TW_DIR_1d": os.path.join("data", "market_data_tw/daily/"),
    "MARKET_DATA_TW_DIR_1wk": os.path.join("data", "market_data_tw/weekly/"),
    "MARKET_DATA_TW_DIR_1mo": os.path.join("data", "market_data_tw/monthly/"),

    # TradingView bulk files (NEW)
    "TW_FILES_DIR": os.path.join("data", "tw_files/"),
    "TW_FILES_DAILY": os.path.join("data", "tw_files/daily/"),
    "TW_FILES_WEEKLY": os.path.join("data", "tw_files/weekly/"),
    "TW_FILES_MONTHLY": os.path.join("data", "tw_files/monthly/"),
}
```

### Update `setup_directories()`:

```python
def setup_directories():
    # ... existing directories ...

    # TradingView data directories
    os.makedirs(PARAMS_DIR["MARKET_DATA_TW_DIR_1d"], exist_ok=True)
    os.makedirs(PARAMS_DIR["MARKET_DATA_TW_DIR_1wk"], exist_ok=True)
    os.makedirs(PARAMS_DIR["MARKET_DATA_TW_DIR_1mo"], exist_ok=True)
    os.makedirs(PARAMS_DIR["TW_FILES_DAILY"], exist_ok=True)
    os.makedirs(PARAMS_DIR["TW_FILES_WEEKLY"], exist_ok=True)
    os.makedirs(PARAMS_DIR["TW_FILES_MONTHLY"], exist_ok=True)
```

---

## 12. FILENAME PARSING STRATEGY

### Expected Filename Patterns

**Daily:**
- `all_stocks _LOHC_2025-10-01.csv`
- Pattern: `all_stocks _LOHC_{YYYY-MM-DD}.csv`

**Weekly:**
- `all_stocks _LOHC_weekly_2025-09-27.csv` (assuming Friday date)
- Pattern: `all_stocks _LOHC_weekly_{YYYY-MM-DD}.csv`

**Monthly:**
- `all_stocks _LOHC_monthly_2025-09-30.csv` (assuming last day of month)
- Pattern: `all_stocks _LOHC_monthly_{YYYY-MM-DD}.csv`

### Parsing Logic

```python
import re
from datetime import datetime

def extract_date_from_filename(filename):
    """
    Extract date from TradingView filename

    Examples:
        'all_stocks _LOHC_2025-10-01.csv' → datetime(2025, 10, 1)
        'all_stocks _LOHC_weekly_2025-09-27.csv' → datetime(2025, 9, 27)
    """
    # Pattern: YYYY-MM-DD anywhere in filename
    pattern = r'(\d{4}-\d{2}-\d{2})'
    match = re.search(pattern, filename)

    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        raise ValueError(f"Could not extract date from filename: {filename}")
```

---

## 13. PERFORMANCE CONSIDERATIONS

### Speed Comparison

**Yahoo Finance Route:**
- 6000 tickers × 0.2s delay = 1200s = 20 minutes (optimistic)
- Reality: 3 hours with API rate limits and errors

**TradingView Route:**
- Parse 1 CSV file: ~5-10 seconds
- Distribute to 6000 files: ~30-60 seconds
- **Total: ~1-2 minutes**

### Optimization Strategies

1. **Batch Processing**: Process multiple tickers before disk I/O
2. **Parallel Writing**: Use multiprocessing for file writes
3. **Memory Efficiency**: Stream large CSV files instead of loading entirely
4. **Caching**: Cache parsed TW data if processing multiple timeframes

---

## 14. TESTING STRATEGY

### Unit Tests

1. **Date Extraction**
   - Test various filename formats
   - Test edge cases (invalid formats)

2. **Data Transformation**
   - Verify LOHC → OHLCV conversion
   - Test with sample TW data

3. **Update Logic**
   - Test new file creation
   - Test appending to existing files
   - Test duplicate date handling

### Integration Tests

1. **End-to-End**
   - Place test TW file in tw_files/daily/
   - Run update process
   - Verify ticker files created/updated in market_data_tw/daily/

2. **Multi-Timeframe**
   - Test daily, weekly, monthly simultaneously

### Manual Testing

1. **Small Dataset**
   - Use test_tickers.csv with 10-20 tickers
   - Verify all files created correctly

2. **Full Dataset**
   - Run on complete TW file (6703 tickers)
   - Monitor for memory issues
   - Verify problematic tickers list

---

## 15. ROLLOUT PLAN

### Phase 1: Core Module Development
- [ ] Create `get_tradingview_data.py`
- [ ] Implement `TradingViewDataRetriever` class
- [ ] Add configuration flags to `user_data.csv`
- [ ] Update `config.py` with TW directories

### Phase 2: Integration
- [ ] Integrate with `main.py`
- [ ] Update `setup_directories()`
- [ ] Add logging and error handling

### Phase 3: Testing
- [ ] Unit tests for core functions
- [ ] Integration test with small dataset
- [ ] Full dataset test

### Phase 4: Documentation
- [ ] Update CLAUDE.md with TW data info
- [ ] Create user guide for TW data workflow
- [ ] Document filename conventions

### Phase 5: Production
- [ ] Run parallel with YF for validation period
- [ ] Monitor for issues
- [ ] Switch to TW as primary source (optional)

---

## 16. FUTURE ENHANCEMENTS (Route 3: Intraday)

### Placeholder for Intraday Implementation

**When implemented, consider:**
- Storage: `data/market_data_intraday/{1m,5m,15m,30m,1h}/`
- File format: Same as daily but with datetime index
- Update frequency: Multiple times per day
- Strategy requirements: Define use cases first

**DO NOT IMPLEMENT YET** - No strategy defined

---

## 17. KEY DECISIONS SUMMARY

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Implementation Location** | `downloadData_v1` | Natural home for market data operations |
| **Module Name** | `get_tradingview_data.py` | Parallel to `get_marketData.py` |
| **Storage Location** | `data/market_data_tw/` | Separate from YF data, already exists |
| **Configuration Approach** | New flags in `user_data.csv` | Consistent with existing pattern |
| **Update Logic** | Date comparison like YF | Proven approach, reuse logic |
| **Data Format** | Standard OHLCV CSV | Consistency with existing system |
| **Parallel Routes** | Independent YF and TW | No modifications to existing YF route |

---

## 18. RISKS & MITIGATIONS

| Risk | Impact | Mitigation |
|------|--------|------------|
| TW file format changes | High | Flexible column matching, version checks |
| Date parsing fails | High | Strict validation, clear error messages |
| Disk space for 2 routes | Medium | Monitor usage, document requirements |
| Duplicate data confusion | Medium | Clear directory separation, documentation |
| Performance with large files | Low | Streaming, batch processing |

---

## 19. QUESTIONS FOR USER CLARIFICATION

1. **Date in TW Files**: Confirm that date is ONLY in filename, not in file content
2. **LOHC vs OHLCV**: Confirm we should store in standard OHLCV format (not LOHC)
3. **Historical Data**: Should we backfill market_data_tw/ with existing TW files?
4. **Ticker Universe**: Use same ticker list as YF route or TW-specific universe?
5. **Metadata**: Should TW route also generate info files like YF route?

---

## 20. NEXT STEPS (AFTER APPROVAL)

1. **Review this plan** with user
2. **Address questions** in Section 19
3. **Begin Phase 1** implementation
4. **Create test dataset** for validation
5. **Implement core module**
6. **Run tests**
7. **Integrate with main.py**

---

## APPENDIX A: Column Mapping Reference

### TradingView → Standard Format

```python
COLUMN_MAPPING = {
    'Symbol': 'ticker',
    'Open 1 day': 'Open',
    'High 1 day': 'High',
    'Low 1 day': 'Low',
    'Price': 'Close',           # TW uses "Price" for Close
    'Volume 1 day': 'Volume'
}

# Flexible matching (in case of variations)
FLEXIBLE_PATTERNS = {
    'open': ['Open 1 day', 'Open', 'open'],
    'high': ['High 1 day', 'High', 'high'],
    'low': ['Low 1 day', 'Low', 'low'],
    'close': ['Price', 'Close', 'close'],
    'volume': ['Volume 1 day', 'Volume', 'volume']
}
```

---

**END OF DOCUMENT**

# Research: Handling Multiple TradingView Files Per Date

## Date: 2025-10-01
## Issue: TradingView separates stocks and ETFs into different CSV files

---

## Current Situation

### Files in Directory:
```
/data/tw_files/daily/
├── all_stocks _OHLCV_2025-09-30.csv  (1.5M, ~6700 stocks)
└── all_ETFs_OHLCV_2025-09-30.csv     (827K, ~3500 ETFs)
```

**Same date, different content:**
- Both files contain data for 2025-09-30
- Stocks file: ~6,700 tickers
- ETFs file: ~3,500 tickers
- Total: ~10,200 tickers to process

### Current Implementation Problem

**`find_latest_tw_file()` (lines 64-106):**
```python
# Current logic:
tw_files = [(file_date, file_path, filename), ...]
tw_files.sort(key=lambda x: x[0], reverse=True)
latest_date, latest_path, latest_filename = tw_files[0]  # ❌ ONLY ONE FILE
return latest_path
```

**Issue**: Returns ONLY the first file for the latest date (alphabetically: `all_ETFs...` comes before `all_stocks...`)

**Result**: Stocks file is ignored, only ETFs are processed!

---

## Column Comparison

Need to verify both files have the same OHLCV columns we need.

### Required Columns (from parse_tw_bulk_file):
- `Symbol`
- `Open 1 day`
- `High 1 day`
- `Low 1 day`
- `Price` (used as Close)
- `Volume 1 day`

### Verification Needed:
- Do both files have these exact columns?
- Are there any column name differences?
- Are data types the same?

---

## Solution Options

### Option 1: Return ALL Files for Latest Date ✅ RECOMMENDED

**Approach:**
```python
def find_all_tw_files_for_date(self, timeframe):
    """
    Find ALL TW files for the most recent date

    Returns:
        list: [(file_date, file_path, filename), ...] for same date
              or empty list if none found
    """
    # ... existing directory check ...

    # Find all CSV files with dates
    tw_files = []
    for filename in files:
        if not filename.endswith('.csv'):
            continue
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            date_str = match.group(1)
            file_path = os.path.join(tw_dir, filename)
            file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            tw_files.append((file_date, file_path, filename))

    if not tw_files:
        return []

    # Find the latest date
    latest_date = max(tw_files, key=lambda x: x[0])[0]

    # Return ALL files with the latest date
    files_for_latest_date = [f for f in tw_files if f[0] == latest_date]

    return files_for_latest_date
```

**Then in update_from_tw_files():**
```python
# Step 1: Find all TW files for latest date
tw_files_list = self.find_all_tw_files_for_date(timeframe)

# Step 2: Extract date (same for all files)
tw_file_date = tw_files_list[0][0]  # Date is same for all

# Step 3: Process each file and merge ticker data
all_ticker_data = {}
for file_date, file_path, filename in tw_files_list:
    print(f"📖 Processing: {filename}")
    ticker_data = self.parse_tw_bulk_file(file_path, file_date)

    # Merge into master dictionary
    all_ticker_data.update(ticker_data)
    print(f"   Total tickers so far: {len(all_ticker_data)}")

# Step 4: Update ticker files with merged data
for ticker, data in all_ticker_data.items():
    self.update_ticker_file(ticker, data, timeframe)
```

**Benefits:**
- ✅ Processes ALL files for the same date
- ✅ Merges stocks + ETFs seamlessly
- ✅ Handles any number of files (stocks, ETFs, futures, etc.)
- ✅ No duplicate ticker issues (dict.update() overwrites)
- ✅ Clean, maintainable code

**Potential Issues:**
- If same ticker appears in both files (e.g., SPY in both stocks and ETFs), the second file overwrites the first
- Solution: This is actually correct behavior - use the most recent data

---

### Option 2: Pattern-Based Multi-File Search

**Approach:**
```python
def find_tw_files_by_patterns(self, timeframe):
    """
    Find TW files matching specific patterns for latest date
    """
    patterns = ['*stocks*', '*ETF*', '*etf*', '*index*']

    # Find latest date across all patterns
    # Find all files matching any pattern for that date
    # Return list of files
```

**Benefits:**
- More control over which files to process

**Drawbacks:**
- ❌ Hardcoded patterns might miss future file types
- ❌ More complex logic
- ❌ Less flexible

---

### Option 3: Sequential Processing with State

**Approach:**
```python
# Process stocks file
stocks_data = parse_tw_bulk_file('all_stocks...')
update_tickers(stocks_data)

# Process ETFs file
etfs_data = parse_tw_bulk_file('all_ETFs...')
update_tickers(etfs_data)
```

**Drawbacks:**
- ❌ Requires knowing file names in advance
- ❌ Not scalable if TradingView adds more file types
- ❌ Duplicate ticker updates (performance issue)

---

## Recommended Implementation

### Phase 1: Modify `find_latest_tw_file()` → `find_all_tw_files_for_latest_date()`

**Changes:**
1. Rename method to reflect it returns multiple files
2. Find the latest date among ALL CSV files
3. Return ALL files matching that date
4. Return as list: `[(date, path, filename), ...]`

### Phase 2: Modify `update_from_tw_files()`

**Changes:**
1. Call new method to get list of files
2. Loop through all files for the date
3. Parse each file into ticker_data dict
4. Merge all ticker_data into master dictionary
5. Update ticker files once with merged data

### Phase 3: Add Logging

**Track:**
- How many files found for latest date
- Tickers per file
- Total unique tickers after merge
- Any duplicate tickers (informational)

---

## Edge Cases to Handle

### 1. Overlapping Tickers
**Scenario**: SPY appears in both stocks and ETFs file
**Solution**: Last file processed wins (dict.update())
**Note**: Document this behavior

### 2. Missing Required Columns in One File
**Scenario**: ETFs file has different column names
**Solution**:
- `parse_tw_bulk_file()` already handles missing columns
- Returns empty dict if columns missing
- Continues with other files

### 3. Different Dates in Directory
**Scenario**:
```
all_stocks_2025-09-30.csv
all_ETFs_2025-09-29.csv  (older)
```
**Solution**: Only process files with the LATEST date (2025-09-30)
**Result**: Stocks processed, old ETFs ignored (correct!)

### 4. Only One File Type Available
**Scenario**: User only downloads stocks, not ETFs
**Solution**: Works as before - processes single file

### 5. Three or More Files
**Scenario**: User adds futures file later
```
all_stocks_2025-09-30.csv
all_ETFs_2025-09-30.csv
all_futures_2025-09-30.csv
```
**Solution**: All three processed automatically (future-proof!)

---

## Column Validation Strategy

Since files might have slightly different columns, strengthen the validation:

```python
def parse_tw_bulk_file(self, filepath, file_date):
    # Current: requires exact column names
    required_columns = ['Symbol', 'Open 1 day', 'High 1 day', 'Low 1 day', 'Price', 'Volume 1 day']

    # Enhancement: Flexible column matching
    # Try exact match first
    # If missing, try variations:
    # - "Open 1 day" or "Open" or "open"
    # - "Price" or "Close" or "close"
    # etc.
```

**But**: If both files already have the same column structure, no changes needed!

---

## Testing Plan

### Test 1: Both Files Present
```
Files: all_stocks_2025-09-30.csv + all_ETFs_2025-09-30.csv
Expected: Both processed, ~10,200 tickers updated
```

### Test 2: Only Stocks File
```
Files: all_stocks_2025-09-30.csv
Expected: Works as before, ~6,700 tickers updated
```

### Test 3: Different Dates
```
Files: all_stocks_2025-09-30.csv + all_ETFs_2025-09-29.csv
Expected: Only latest date (09-30) processed, stocks only
```

### Test 4: Same Ticker in Both Files
```
Stocks file: SPY with price 450.00
ETFs file: SPY with price 450.01
Expected: ETFs file data used (last one wins)
```

---

## Performance Considerations

### Current (Single File):
- Parse 1 file: ~5-10 seconds
- Update tickers: ~30-60 seconds
- **Total: ~1-2 minutes**

### With Multiple Files:
- Parse 2 files: ~10-20 seconds
- Merge dictionaries: <1 second
- Update tickers: ~30-60 seconds (same, single loop)
- **Total: ~1-2 minutes** (minimal overhead)

**Conclusion**: No significant performance impact

---

## Summary

### Recommended Approach: Option 1

**Implementation Steps:**
1. Rename `find_latest_tw_file()` → `find_all_tw_files_for_latest_date()`
2. Return list of ALL files with latest date
3. Loop through files, parse each one
4. Merge ticker_data dictionaries
5. Update ticker files with merged data

**Benefits:**
- ✅ Future-proof (handles any number of files)
- ✅ Automatic (no hardcoded file names)
- ✅ Clean code (minimal changes needed)
- ✅ Fast (minimal overhead)
- ✅ Handles edge cases gracefully

**Code Impact:**
- Modify: `find_latest_tw_file()` method (~20 lines)
- Modify: `update_from_tw_files()` method (~15 lines)
- Add: Logging for multiple file processing (~5 lines)
- **Total: ~40 lines changed**

---

## Alternative: Quick Fix

If you want minimal code changes:

**Keep existing method, just call it in a loop:**
```python
# Find all CSV files in directory
all_files = [f for f in os.listdir(tw_dir) if f.endswith('.csv')]

# Group by date
files_by_date = {}
for filename in all_files:
    date = extract_date_from_filename(filename)
    if date not in files_by_date:
        files_by_date[date] = []
    files_by_date[date].append(filename)

# Get latest date
latest_date = max(files_by_date.keys())

# Process all files for latest date
for filename in files_by_date[latest_date]:
    ticker_data = parse_tw_bulk_file(filepath, latest_date)
    # update tickers...
```

**But**: Option 1 is cleaner and more maintainable.

---

**END OF RESEARCH**

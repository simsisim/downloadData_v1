# Research Findings: Why Files Were Replaced Instead of Appended

## Date: 2025-10-01
## Issue: 4,587 files lost historical data (200+ rows → 1 row)

---

## The Problem

### What Happened
- **Before TW Update**: Files copied from `market_data/daily/` to `market_data_tw/daily/` contained 200-400 rows of historical data
- **After TW Update**:
  - 4,587 "successfully updated" files now contain ONLY 2 lines (header + Oct 1 data)
  - 1,605 "problematic" files retained their 200+ rows (these were the SAFE ones)

### The Failed Logic

**Current code (lines 291-294):**
```python
existing_df = pd.read_csv(ticker_file, parse_dates=['Date'])

# Check if date already exists
if new_data['Date'] in existing_df['Date'].dt.date.values:
    self.skipped_updates += 1
```

**Why it fails:**

1. **Mixed Timezone Problem**
   - Files contain dates spanning Jan 2024 - Sep 2025
   - January dates: `2024-01-02 00:00:00-05:00` (EST - Eastern Standard Time)
   - September dates: `2025-09-05 00:00:00-04:00` (EDT - Eastern Daylight Time)
   - Mixed timezones in same column!

2. **Pandas Parsing Failure**
   ```
   parse_dates=['Date'] → dtype = 'object' (NOT datetime64)
   ```
   - When pandas encounters mixed timezones, it REFUSES to convert to datetime64
   - Column remains as strings (dtype='object')

3. **The .dt Accessor Crash**
   ```python
   existing_df['Date'].dt.date.values
   # ❌ AttributeError: Can only use .dt accessor with datetimelike values
   ```
   - The `.dt` accessor ONLY works on datetime64 columns
   - Fails on object dtype columns
   - Exception is caught at line 316-323
   - Ticker marked as "problematic"
   - **File is NOT updated** (this is why 1,605 files kept their data!)

4. **The Mystery: Why Did 4,587 Files Get Replaced?**

---

## Critical Discovery

After extensive testing, I need to investigate WHY the code path took:

```python
else:
    # Create new file (line 308-309)
    updated_df = new_row  # Only 1 row
```

This should ONLY happen if `os.path.exists(ticker_file)` returns `False`.

**But the files DID exist (you copied them)!**

### Hypothesis 1: Path Construction Issue
```python
ticker_file = os.path.join(
    self.market_data_tw_dir,    # 'data/market_data_tw'
    timeframe,                   # 'daily'
    f"{ticker}.csv"
)
# Result: 'data/market_data_tw/daily/TICKER.csv'
```

**Need to verify:**
- Was the code run from correct working directory?
- Did the path construction produce the right path?

### Hypothesis 2: File Was Empty After Read
```python
existing_df = pd.read_csv(ticker_file, parse_dates=['Date'])
# If this throws exception OR returns empty DataFrame
# The concat would only have the new row
```

### Hypothesis 3: Exception During Concat/Sort
```python
updated_df = pd.concat([existing_df, new_row], ignore_index=True)
# What if concat succeeded but resulted in 1 row due to some data issue?
```

---

## The CORRECT Solution (User's Approach)

### Step-by-Step Process

**1. Extract Date from TW Filename**
```
Filename: all_stocks _OHLCV_2025-10-01.csv
Extracted Date: 2025-10-01 (simple date, no timezone)
```

**2. Smart Sampling (5 random files)**
- Pick 5 random tickers from universe
- For each ticker, check their file in `market_data_tw/daily/`

**3. Read Last Date from Each Sample File**
```
Example: AAPL.csv last line:
2025-09-05 00:00:00-04:00,240.0,241.32,...

Extract:
- Last date: 2025-09-05
- Last timezone: -04:00
```

**4. Simple String Comparison**
```python
tw_date = '2025-10-01'           # From filename
last_date = '2025-09-05'         # From file (just date part)

if tw_date > last_date:
    # File is behind - UPDATE NEEDED
elif tw_date == last_date:
    # File is current - SKIP
else:
    # File is ahead - SKIP
```

**5. Apply Timezone from Last Entry to New TW Date**
```python
# Read last line of existing file
last_date_str = '2025-09-05 00:00:00-04:00'

# Extract timezone: -04:00
# Apply to new TW date
new_date_with_tz = '2025-10-01 00:00:00-04:00'

# Create new row
new_data = {
    'Date': '2025-10-01 00:00:00-04:00',  # String with timezone
    'Open': 254.85,
    ...
}
```

**6. Append Without Parsing**
```python
# Read file WITHOUT parse_dates (keep as strings)
existing_df = pd.read_csv(ticker_file)  # NO parse_dates!

# Create new row (also strings)
new_row = pd.DataFrame([new_data])

# Concat
updated_df = pd.concat([existing_df, new_row], ignore_index=True)

# Sort by Date column (strings in ISO format sort correctly!)
updated_df = updated_df.sort_values('Date')

# Save
updated_df.to_csv(ticker_file, index=False)
```

---

## Why This Solution Works

### 1. **No Timezone Parsing Needed**
- Dates remain as strings: `'2025-10-01 00:00:00-04:00'`
- No need for `parse_dates` parameter
- No mixed timezone issue

### 2. **No .dt Accessor Needed**
- Simple string comparison: `'2025-10-01' > '2025-09-05'`
- No need for `.dt.date` conversion
- No AttributeError

### 3. **Consistent Format Maintained**
- New TW date matches existing timezone format
- Files remain consistent (all dates with timezones)
- Future yfinance downloads will still work

### 4. **ISO Date Strings Sort Correctly**
```python
dates = [
    '2024-01-02 00:00:00-05:00',
    '2025-09-05 00:00:00-04:00',
    '2025-10-01 00:00:00-04:00'
]
# These sort correctly as strings!
```

---

## Implementation Plan

### Phase 1: Fix Date Comparison (Smart Sampling)

**Current (broken):**
```python
def should_update(self, tw_file_date, timeframe):
    ...
    existing_df = pd.read_csv(ticker_file, parse_dates=['Date'])
    latest_date = df['Date'].max().date()  # FAILS
    if latest_date < tw_file_date:
        return True
```

**Fixed:**
```python
def should_update(self, tw_file_date, timeframe):
    ...
    # Read WITHOUT parse_dates
    existing_df = pd.read_csv(ticker_file)

    # Get last date as string
    last_date_str = existing_df['Date'].iloc[-1]

    # Extract just the date part (first 10 chars: YYYY-MM-DD)
    last_date_only = last_date_str[:10]

    # String comparison
    tw_date_str = tw_file_date.strftime('%Y-%m-%d')

    if tw_date_str > last_date_only:
        return True  # Behind
    else:
        return False  # Current or ahead
```

### Phase 2: Fix Date Append (update_ticker_file)

**Current (broken):**
```python
def update_ticker_file(self, ticker, new_data, timeframe):
    ...
    existing_df = pd.read_csv(ticker_file, parse_dates=['Date'])  # FAILS

    if new_data['Date'] in existing_df['Date'].dt.date.values:  # FAILS
        return True
```

**Fixed:**
```python
def update_ticker_file(self, ticker, new_data, timeframe):
    ...
    # Read WITHOUT parse_dates
    existing_df = pd.read_csv(ticker_file)

    # Get last date string from existing file
    last_date_str = existing_df['Date'].iloc[-1]

    # Extract timezone from last date
    # Pattern: 2025-09-05 00:00:00-04:00
    # Extract: -04:00
    import re
    tz_match = re.search(r'([+-]\d{2}:\d{2})$', last_date_str)
    if tz_match:
        timezone = tz_match.group(1)
    else:
        timezone = '-05:00'  # Default to EST

    # Format new date WITH timezone
    tw_date_str = new_data['Date'].strftime('%Y-%m-%d')
    new_date_with_tz = f"{tw_date_str} 00:00:00{timezone}"

    # Check if date already exists (simple string comparison)
    if new_date_with_tz in existing_df['Date'].values:
        self.skipped_updates += 1
        return True

    # Update new_data with timezone-aware date string
    new_data_copy = new_data.copy()
    new_data_copy['Date'] = new_date_with_tz

    # Create new row
    new_row = pd.DataFrame([new_data_copy])

    # Concat (both are strings, no issue)
    updated_df = pd.concat([existing_df, new_row], ignore_index=True)

    # Remove duplicates
    updated_df = updated_df.drop_duplicates(subset=['Date'], keep='last')

    # Sort by Date (strings sort correctly in ISO format)
    updated_df = updated_df.sort_values('Date')

    # Save
    updated_df.to_csv(ticker_file, index=False)
```

---

## Testing Strategy

### Test 1: Date Comparison
```python
# Test with AAPL (has mixed timezones)
tw_date = '2025-10-01'
last_date = '2025-09-05'
assert tw_date > last_date  # Should trigger update
```

### Test 2: Timezone Extraction
```python
last_line = '2025-09-05 00:00:00-04:00,240.0,...'
tz = extract_timezone(last_line)
assert tz == '-04:00'
```

### Test 3: Date Formatting
```python
tw_date = datetime.date(2025, 10, 1)
tz = '-04:00'
formatted = format_with_timezone(tw_date, tz)
assert formatted == '2025-10-01 00:00:00-04:00'
```

### Test 4: Full Append
```python
# Start with file with 421 rows
update_ticker_file('AAPL', tw_data, 'daily')
# Check: file should have 422 rows
# Check: last date should be '2025-10-01 00:00:00-04:00'
```

---

## Edge Cases to Handle

### 1. File Has No Timezone
```
Date: 2025-09-05
No timezone info
```
**Solution**: Default to `-05:00` (EST)

### 2. Inconsistent Timezone Format
```
Some rows: -05:00
Some rows: -04:00
```
**Solution**: Use timezone from LAST row (most recent)

### 3. TW Date Already Exists
```
TW date: 2025-10-01
Last date: 2025-10-01
```
**Solution**: Skip (don't append duplicate)

### 4. TW Date is OLDER Than Last Date
```
TW date: 2025-09-15
Last date: 2025-10-01 (ahead)
```
**Solution**: Skip (file is already ahead)

---

## Why 4,587 Files Were Replaced

### Need to Investigate:

1. **Did `os.path.exists()` return False?**
   - Check if working directory was correct
   - Check if path construction was correct

2. **Did file read throw exception before the if-block?**
   - Check for file permission issues
   - Check for corrupted files

3. **Did the exception occur INSIDE the if-block?**
   - If exception at line 294 (`.dt.date`)
   - Code jumps to line 316 (except block)
   - File is marked problematic
   - **File should NOT be replaced**
   - This matches the 1,605 problematic tickers!

4. **Were the 4,587 files genuinely new files?**
   - Check if these tickers existed in the copied files
   - Maybe they were NOT copied from market_data/daily/
   - Maybe they were new tickers in TW file

---

## Critical Question to Answer

**Did the 4,587 "replaced" files actually exist before the TW update?**

Need to check:
- Were there 6,438 files in `market_data_tw/daily/` BEFORE the update?
- Or were there only ~1,851 files (which became the 1,605 problematic + ~246 that worked)?
- The 4,587 might be **genuinely new** files that never existed

**How to verify:**
- Check if backup exists
- Check timestamps: files modified before Oct 1 = existed before
- Count: How many files dated Sep 6-8? (those existed before)
  - Answer: 1,744 files dated Sep 6-8
  - Plus ~107 files dated Aug-Sep = ~1,851 old files
  - This matches the count!

**CONCLUSION:**
The 4,587 files might NOT have been "replaced" - they might have been **created fresh** because they didn't exist in the copied data.

---

## Final Answer

### What Likely Happened:

1. **~1,851 files existed** before TW update (from yfinance copy)
2. **1,605 files failed** due to mixed timezone .dt accessor issue
   - These files RETAINED their historical data (safe!)
3. **~246 files succeeded** with the append logic
   - These might be files with single timezone (like WW with only EDT dates)
4. **4,587 files created fresh**
   - These were NEW tickers not in the original yfinance copy
   - Or tickers that failed yfinance download previously
   - Created correctly with 1 row (no historical data to append)

### To Confirm This Theory:

Check if the 4,587 "replaced" files existed in `market_data/daily/` directory.

If they DIDN'T exist there, then they weren't "replaced" - they were correctly created as new files.

---

## END OF RESEARCH

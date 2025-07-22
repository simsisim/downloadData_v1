
PROGRAM STRUCTURE:
project_root/
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── get_marketData.py    - DOWNLOADS/UPDATES HISTORICAL MARKET DATA FROM YF
│   ├── get_tickers.py       - DOWNLOADS STOCKS TICKERS FROM VARIOUS FREE RESOURCES: nasadq webpage, wikipedia etc..
│   ├── combined_tickers.py  - COMBINES TICKERS (AS IN CONFIG.PY) AS A PREPROCESSING FOR DOWNLOAD. THE TICKERS_INDEXES (user_choice = 19) ARE ALWAYS INCLUDED
│   └── user_defined_data.py - READS THE USER INPUT given in user_data.csv
├── data/
│   ├── tickers/(RESULTS)
│   │   ├── sp500_tickers.csv
│   │   ├── nasdaq100_tickers.csv
│   │   ├── iwm1000_tickers.csv
│   │   ├── nasdaq_all_tickers.csv
│   │   ├── indexes_tickers.csv
│   │   └── combined_tickers_{user_choice}.csv (user_choice + choice_16)
│   │   └── problematic_tickers_{user_choice}.csv
│   │   └── combined_tickers_OK_{user_choice}.csv - tickers without errors (for further data processing)
│   │
│   └── market_data/(RESULTS)
│       ├── {ticker}.csv (individual stock data files)
│       ├── info_{user_choice}.csv 
│       └── problematic_tickers_{user_choice}.csv
│
├── main.py
├── requirements.txt
├── README.md
└── user_data.csv
└── IndexesTickersManualGeneration - this is used to generate indexes_tickers_manual.csv (user input)




Input the type of stocks that you wanat to download: user_data.csv

NOTE:I cannot find a place where to download tickers for main indices from: the tickers from indexes_tickers_manual(the file was created manually from https://finance.yahoo.com/markets/world-indices/) is created manually and it contains main indices tickers.


#################################################################################
#################################################################################
################################################################################
FURTHER WORK:

Download main commodities: + BTC
User input variable is going to be read from a csv file.

#################################################################################
#################################################################################
#################################################################################
ONGOING NOTES:

>>> import yfinance as yf
>>> 
>>> # Create a Ticker object for a stock (e.g., Apple)
>>> ticker = yf.Ticker("AAPL")
>>> 
>>> # Get the info dictionary
>>> info = ticker.info
>>> 
>>> # Print the keys (available info fields)
>>> for key in info.keys():
...     print(key)
    print(info.get('industry', 'N/A'))
    print(info.get('sector', 'N/A'))
... 
address1
city
state
zip
country
phone
website
industry
industryKey
industryDisp
sector
sectorKey
sectorDisp
longBusinessSummary
fullTimeEmployees
companyOfficers
auditRisk
boardRisk
compensationRisk
shareHolderRightsRisk
overallRisk
governanceEpochDate
compensationAsOfEpochDate
irWebsite
maxAge
priceHint
previousClose
open
dayLow
dayHigh
regularMarketPreviousClose
regularMarketOpen
regularMarketDayLow
regularMarketDayHigh
dividendRate
dividendYield
exDividendDate
payoutRatio
fiveYearAvgDividendYield
beta
trailingPE
forwardPE
volume
regularMarketVolume
averageVolume
averageVolume10days
averageDailyVolume10Day
bid
ask
bidSize
askSize
marketCap
fiftyTwoWeekLow
fiftyTwoWeekHigh
priceToSalesTrailing12Months
fiftyDayAverage
twoHundredDayAverage
trailingAnnualDividendRate
trailingAnnualDividendYield
currency
enterpriseValue
profitMargins
floatShares
sharesOutstanding
sharesShort
sharesShortPriorMonth
sharesShortPreviousMonthDate
dateShortInterest
sharesPercentSharesOut
heldPercentInsiders
heldPercentInstitutions
shortRatio
shortPercentOfFloat
impliedSharesOutstanding
bookValue
priceToBook
lastFiscalYearEnd
nextFiscalYearEnd
mostRecentQuarter
earningsQuarterlyGrowth
netIncomeToCommon
trailingEps
forwardEps
lastSplitFactor
lastSplitDate
enterpriseToRevenue
enterpriseToEbitda
52WeekChange
SandP52WeekChange
lastDividendValue
lastDividendDate
exchange
quoteType
symbol
underlyingSymbol
shortName
longName
firstTradeDateEpochUtc
timeZoneFullName
timeZoneShortName
uuid
messageBoardId
gmtOffSetMilliseconds
currentPrice
targetHighPrice
targetLowPrice
targetMeanPrice
targetMedianPrice
recommendationMean
recommendationKey
numberOfAnalystOpinions
totalCash
totalCashPerShare
ebitda
totalDebt
quickRatio
currentRatio
totalRevenue
debtToEquity
revenuePerShare
returnOnAssets
returnOnEquity
freeCashflow
operatingCashflow
earningsGrowth
revenueGrowth
grossMargins
ebitdaMargins
operatingMargins
financialCurrency
trailingPegRatio
#################################################################################
#################################################################################
#################################################################################   


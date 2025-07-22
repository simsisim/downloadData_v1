
import os 
import yfinance as yf

print('Testing yfinance is working ....download AAPL data')

# Create a Ticker object for AAPL
test = yf.Ticker('AAPL')

# Specify your desired start and end dates
start_date = '2023-01-01'
end_date = '2023-05-31'

# Download data between start and end date
data = test.history(start=start_date, end=end_date)

print(data)  # Print all data
print("\nClosing prices:")
print(data['Close'])  # Print closing prices
print("\nVolume:")
print(data['Volume'])  # Print volume data


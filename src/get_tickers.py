import ftplib
import re
import csv
import pandas as pd
import os

class TickerRetriever:
    #def __init__(self):
    #    os.makedirs('./tickers', exist_ok=True)
    #    self.sp500_file_path = "sp500_tickers.csv"
    #    self.nasdaq100_file_path = "nasdaq100_tickers.csv"
    #    self.iwm1000_file_path = "iwm1000_tickers.csv"
    #    self.nasdaq_all_file_path = "nasdaq_all_tickers.csv"
    #    self.combined_file_path = "combined_tickers.csv"
    #    self.ftp_server = "ftp.nasdaqtrader.com"
    #    self.remote_file_path = "/symboldirectory/nasdaqtraded.txt"
    #    self.local_file_path = "nasdaqtraded.txt"
    #    self.indexes_file_path  = "indexes_tickers.csv"

    def __init__(self, tickers_folder='data/tickers'):
        self.tickers_folder = tickers_folder
        os.makedirs(f'./{self.tickers_folder}', exist_ok=True)
        self.sp500_file_path = os.path.join(self.tickers_folder, "sp500_tickers.csv")
        self.sp600_file_path = os.path.join(self.tickers_folder, "sp600_tickers.csv")
        self.nasdaq100_file_path = os.path.join(self.tickers_folder, "nasdaq100_tickers.csv")
        self.iwm1000_file_path = os.path.join(self.tickers_folder, "iwm1000_tickers.csv")
        self.nasdaq_all_file_path = os.path.join(self.tickers_folder, "nasdaq_all_tickers.csv")
        #self.combined_file_path = os.path.join(self.tickers_folder, "combined_tickers.csv")
        self.indexes_file_path = os.path.join(self.tickers_folder, "indexes_tickers.csv")
        self.portofolio_file_path = os.path.join(self.tickers_folder, "portofolio_tickers.csv")
    
        self.ftp_server = "ftp.nasdaqtrader.com"
        self.remote_file_path = "/symboldirectory/nasdaqtraded.txt"
        self.local_file_path = os.path.join(self.tickers_folder, "nasdaqtraded.txt")



    def download_nasdaq_file(self):
        ftp = ftplib.FTP(self.ftp_server)
        ftp.login()
        ftp.sendcmd("TYPE i")
        with open(self.local_file_path, 'wb') as local_file:
            ftp.retrbinary(f"RETR {self.remote_file_path}", local_file.write)
        ftp.quit()
        print(f"File downloaded successfully to {self.local_file_path}")

    def get_nasdaq_all_tickers(self):
        tickers = {}
        with open(self.local_file_path, 'r') as file:
            results = file.readlines()
        for entry in results[1:]:
            values = entry.strip().split('|')
            if len(values) > 7:
                ticker = values[1]
                if re.match(r'^[A-Z]+$', ticker) and values[5] == "N" and values[7] == "N":
                    tickers[ticker] = {
                        "ticker": ticker,
                        "sector": "UNKNOWN",
                        "industry": "UNKNOWN",
                        "universe": self.exchange_from_symbol(values[3])
                    }
        return list(tickers.keys())

    @staticmethod
    def exchange_from_symbol(symbol):
        if symbol == 'Q':
            return 'NASDAQ'
        elif symbol == 'N':
            return 'NYSE'
        else:
            return 'OTHER'

    def get_sp500_tickers(self):
        url = 'http://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        table = pd.read_html(url)[0]
        return table['Symbol'].tolist()
    
    def get_sp600_tickers(self):
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_600_companies'
        table = pd.read_html(url)[0]
        return table['Symbol'].tolist()
    

    def get_nasdaq100_tickers(self):
        url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        table = pd.read_html(url)[4]
        return table['Ticker'].tolist()

    def get_iwm1000_tickers(self):
        url = 'https://en.wikipedia.org/wiki/Russell_1000_Index'
        table = pd.read_html(url)[3]
        return table['Symbol'].tolist()
              
    def get_indexes_tickers(self):
       file_path_manual = 'indexes_tickers_manual.csv'
       table = pd.read_csv(file_path_manual)
       return table['ticker'].tolist() 
   
    def get_portofolio_tickers(self):
       file_path_manual = 'myPortofolio_io.csv'
       table = pd.read_csv(file_path_manual)
       return table['ticker'].tolist() 

    def save_tickers(self, tickers, file_path):
        df = pd.DataFrame({'ticker': tickers})
        df.to_csv(file_path, index=False)
        print(f'Saved tickers to {file_path}')


            
    def fetch_and_save_all(self):

        sp500_tickers = self.get_sp500_tickers()
        sp600_tickers = self.get_sp600_tickers()
        nasdaq100_tickers = self.get_nasdaq100_tickers()
        iwm1000_tickers = self.get_iwm1000_tickers()
        indexes_tickers = self.get_indexes_tickers()
        portofolio_tickers = self.get_portofolio_tickers()
        self.download_nasdaq_file()
        nasdaq_all_tickers = self.get_nasdaq_all_tickers()
       
           #print(f'Saved index tickers to {self.indexes_file_path}')

        self.save_tickers(sp500_tickers, self.sp500_file_path)
        self.save_tickers(sp600_tickers, self.sp500_file_path)
        self.save_tickers(nasdaq100_tickers, self.nasdaq100_file_path)
        self.save_tickers(iwm1000_tickers, self.iwm1000_file_path)
        self.save_tickers(nasdaq_all_tickers, self.nasdaq_all_file_path)
        self.save_tickers(indexes_tickers, self.indexes_file_path)       
        self.save_tickers(portofolio_tickers, self.portofolio_file_path)       

        sp500Nasdaq_tickers = list(set(sp500_tickers + nasdaq100_tickers))
        #self.save_tickers(sp500Nasdaq_tickers, self.combined_file_path)


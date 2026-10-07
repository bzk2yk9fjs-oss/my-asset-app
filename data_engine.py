import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
import json
import datetime
import pytz
import requests
import math
from config import KOR_NAMES

# ==========================================
# 네트워크 타임아웃 방어막 & 봇 탐지 우회 신분증
# ==========================================
class TimeoutHTTPAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.pop('timeout', 10)
        super().__init__(*args, **kwargs)
    def send(self, request, **kwargs):
        kwargs['timeout'] = kwargs.get('timeout') or self.timeout
        return super().send(request, **kwargs)

yf_session = requests.Session()
yf_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

adapter = TimeoutHTTPAdapter(timeout=10)
yf_session.mount("https://", adapter)
yf_session.mount("http://", adapter)

# ==========================================
# 1. 백엔드 데이터베이스 & 캐시 캡슐화 구역
# ==========================================
@st.cache_data(ttl=30)
def load_data():
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("내 주식 장부").sheet1
        return pd.DataFrame(sheet.get_all_records())
    except Exception as e:
        return pd.DataFrame()

def add_trade(date_str, ticker, trade_type, qty, price, fx, group):
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("내 주식 장부").sheet1
        sheet.append_row([str(date_str), str(ticker).upper(), str(trade_type), float(qty), float(price), float(fx), str(group)])
        return True
    except Exception:
        return False

@st.cache_data(ttl=30)
def get_macro_data():
    macros = {}
    symbols = {"USDKRW": "USDKRW=X", "TNX": "^TNX", "WTI": "CL=F"}
    for key, sym in symbols.items():
        try:
            tk = yf.Ticker(sym, session=yf_session)
            live = float(tk.fast_info.last_price)
            if math.isnan(live): live = 0.0
            prev = float(tk.fast_info.previous_close)
            if math.isnan(prev): prev = 0.0
            
            if key == "TNX" and live > 10:
                live /= 10
                prev /= 10
            change = live - prev
            pct = (change / prev) * 100 if prev > 0 else 0.0
            macros[key] = {"live": live, "change": change, "pct": pct}
        except:
            macros[key] = {"live": 0.0, "change": 0.0, "pct": 0.0}
    return macros

@st.cache_data(ttl=30, show_spinner=False)
def fetch_market_data(tickers_tuple):
    market_data = {'STOCKS': {}}
    ny_tz = pytz.timezone('America/New_York')
    
    sp500_5m = yf.Ticker("^GSPC", session=yf_session).history(period="15d", interval="5m")
    if not sp500_5m.empty:
        if sp500_5m.index.tz is None: 
            sp500_5m.index = sp500_5m.index.tz_localize('UTC').tz_convert(ny_tz)
        else: 
            sp500_5m.index = sp500_5m.index.tz_convert(ny_tz)
            
        sp500_reg = sp500_5m.between_time('09:30', '16:00')
        trading_dates = sorted(list(set(sp500_reg.index.date)))
    else:
        trading_dates = []
        sp500_reg = pd.DataFrame()
        
    market_data['trading_dates'] = trading_dates
    market_data['sp500_reg'] = sp500_reg
    market_data['sp500_5m'] = sp500_5m

    for tk in tickers_tuple:
        tk_obj = yf.Ticker(tk, session=yf_session)
        
        try: df_1d = tk_obj.history(period="15d", interval="1d")
        except: df_1d = pd.DataFrame()
        
        try: df_5m = tk_obj.history(period="15d", interval="5m", prepost=True)
        except: df_5m = pd.DataFrame()
        
        if not df_1d.empty:
            if df_1d.index.tz is None: df_1d.index = df_1d.index.tz_localize(ny_tz)
            else: df_1d.index = df_1d.index.tz_convert(ny_tz)
            df_1d['date'] = df_1d.index.date
            
        if not df_5m.empty:
            if df_5m.index.tz is None: df_5m.index = df_5m.index.tz_localize('UTC').tz_convert(ny_tz)
            else: df_5m.index = df_5m.index.tz_convert(ny_tz)
            
        market_data['STOCKS'][tk] = {'df_1d': df_1d, 'df_5m': df_5m}
        
    return market_data

@st.cache_data(ttl=86400)
def get_all_us_tickers():
    core_etf_tickers = ['SPY', 'QQQ', 'DIA', 'TQQQ', 'SQQQ', 'SOXL', 'SOXS', 'UPRO', 'SSO', 'QLD', 'SOXX', 'USD', 'SCHD', 'JEPI', 'TLT', 'VOO', 'SGOV', 'SNXX', 'NVDL', 'TSLL', 'CONL']
    core_etfs = [f"{tk} | {KOR_NAMES.get(tk, tk)}" for tk in core_etf_tickers]
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            ticker_list = core_etfs.copy()
            for item in data.values():
                tk = item['ticker'].replace('-', '.')
                if tk not in core_etf_tickers:
                    ticker_list.append(f"{tk} | {KOR_NAMES.get(tk, item['title'])}")
            return ["직접 입력 (티커 수동 입력)"] + sorted(list(set(ticker_list)))
        else: raise Exception()
    except:
        fallback_tk_list = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'META', 'GOOGL', 'KO', 'BAC', 'NEE', 'LMT', 'IBM', 'RGTI', 'ARQQ', 'SPCX']
        return ["직접 입력 (티커 수동 입력)"] + sorted(list(set(core_etfs + [f"{tk} | {KOR_NAMES.get(tk, tk)}" for tk in fallback_tk_list])))

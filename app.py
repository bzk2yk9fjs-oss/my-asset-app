import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
import json
import plotly.express as px
import streamlit.components.v1 as components
import datetime
import pytz
import requests
import math

st.set_page_config(page_title="한결 퀀트 포트폴리오", layout="wide", page_icon="📈")

st.title("📈 한결 퀀트 & 매크로 자산관리 비서")
st.write("V5.25: 수익률 정밀도 및 시황 브리핑 복구 (V4.14 독립 시계열 및 라이브 전광판 엔진 롤백)")

# ==========================================
# 세션 스테이트 초기화 (중복 클릭 방지용)
# ==========================================
if 'last_trade_hash' not in st.session_state:
    st.session_state['last_trade_hash'] = None

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
# 0. 스마트 한글 사전
# ==========================================
KOR_NAMES = {
    'VOO': '뱅가드 S&P 500', 'SGOV': '미국 0-3개월 초단기채', 'KO': '코카콜라', 
    'BAC': '뱅크오브아메리카', 'NEE': '넥스트에라 에너지', 'LMT': '록히드 마틴', 
    'GOOGL': '알파벳 A', 'IBM': 'IBM', 'SPCX': '스페이스X', 
    'RGTI': '리게티 컴퓨팅', 'ARQQ': '아킷 퀀텀',
    'AAPL': '애플', 'MSFT': '마이크로소프트', 'AMZN': '아마존닷컴', 'NVDA': '엔비디아', 
    'TSLA': '테슬라', 'META': '메타 플랫폼스', 'BRK.B': '버크셔 해서웨이', 'AVGO': '브로드컴', 
    'TSM': 'TSMC', 'LLY': '일라이 릴리', 'JPM': 'JP모건 체이스', 'V': '비자', 
    'XOM': '엑슨모빌', 'UNH': '유나이티드헬스', 'PG': '프록터 앤 갬블 (P&G)', 
    'MA': '마스터카드', 'JNJ': '존슨앤존슨', 'HD': '홈디포', 'MRK': '머크', 'CVX': '쉐브론',
    'SPY': 'SPDR S&P 500', 'QQQ': '인베스코 QQQ', 'DIA': 'SPDR 다우존스',
    'SCHD': '슈왑 배당 ETF (SCHD)', 'JEPI': 'JP모건 커버드콜 (JEPI)', 'TLT': '미국 20년 이상 장기채',
    'TQQQ': '프로셰어즈 TQQQ (나스닥 3X)', 'SQQQ': '프로셰어즈 SQQQ (인버스 3X)', 
    'SOXL': '디렉시온 SOXL (반도체 3X)', 'SOXS': '디렉시온 SOXS (인버스 3X)',
    'SSO': '프로셰어즈 SSO (S&P 500 2X)', 'UPRO': '프로셰어즈 UPRO (S&P 500 3X)',
    'QLD': '프로셰어즈 QLD (나스닥 2X)', 'SOXX': 'iShares 반도체 ETF', 'USD': '프로셰어즈 반도체 2X',
    'SNXX': '트레이더 샌디스크 2X', 'NVDL': '그래니트셰어즈 엔비디아 2X', 
    'TSLL': '디렉시온 테슬라 1.5X', 'CONL': '그래니트셰어즈 코인베이스 2X',
    'LEU': '센트러스 에너지'
}

# ==========================================
# 1. 백엔드 데이터베이스 & 캐시 캡슐화 구역
# ==========================================
def get_color_text(val, is_percent=True):
    if pd.isna(val) or val is None: return ":gray[데이터 없음]"
    sign = "+" if val > 0 else ""
    fmt = f"{val:.2f}"
    if is_percent: res = f"{sign}{fmt}%"
    else: res = f"{sign}${abs(val):.2f}"
    if val > 0: return f":green[{res}]"
    elif val < 0: return f":red[{res}]"
    else: return f":gray[{res}]"

def get_macro_color_text(val, is_percent=True, prefix="", suffix=""):
    if pd.isna(val) or val is None: return ":gray[데이터 없음]"
    sign = "+" if val > 0 else ""
    fmt = f"{val:.2f}"
    if is_percent: res = f"{sign}{fmt}%"
    else: res = f"{sign}{prefix}{abs(val):.2f}{suffix}"
    if val > 0: return f":red[{res}]"
    elif val < 0: return f":blue[{res}]"
    else: return f":gray[{res}]"

@st.cache_data(ttl=30)
def load_data():
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("내 주식 장부").sheet1
        return pd.DataFrame(sheet.get_all_records())
    except Exception as e:
        raise Exception("Google API Error")

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
    market_data = {'SP500_hist': pd.DataFrame(), 'STOCKS': {}, 'LAST_TRADE_TIME': None}
    ny_tz = pytz.timezone('America/New_York')
    
    sp_obj = yf.Ticker("^GSPC", session=yf_session)
    try: sp_hist = sp_obj.history(period="15d", interval="1d")
    except: sp_hist = pd.DataFrame()
    
    if sp_hist.empty: 
        try: 
            sp_obj = yf.Ticker("SPY", session=yf_session)
            sp_hist = sp_obj.history(period="15d", interval="1d")
        except: sp_hist = pd.DataFrame()
        
    if not sp_hist.empty:
        if sp_hist.index.tz is None: sp_hist.index = sp_hist.index.tz_localize(ny_tz)
        else: sp_hist.index = sp_hist.index.tz_convert(ny_tz)
        market_data['SP500_hist'] = sp_hist
        
        try:
            last_ts = getattr(sp_obj.fast_info, 'lastTradeTime', None)
            if not last_ts: last_ts = getattr(sp_obj.fast_info, 'last_trade_time', None)
            if last_ts is not None:
                if isinstance(last_ts, (int, float)):
                    dt_obj = datetime.datetime.fromtimestamp(last_ts, pytz.utc)
                    market_data['LAST_TRADE_TIME'] = dt_obj.astimezone(ny_tz)
                else:
                    if hasattr(last_ts, 'tzinfo') and last_ts.tzinfo is not None:
                        market_data['LAST_TRADE_TIME'] = last_ts.astimezone(ny_tz)
                    else:
                        market_data['LAST_TRADE_TIME'] = pytz.utc.localize(last_ts).astimezone(ny_tz)
        except Exception:
            market_data['LAST_TRADE_TIME'] = None
        
    for tk in tickers_tuple:
        tk_obj = yf.Ticker(tk, session=yf_session)
        
        # [V5.25 핵심 복구] 5분봉의 불완전성을 버리고, V4.14의 완벽한 전광판 라이브 가격만 사용
        try:
            c_price = float(tk_obj.fast_info.last_price)
            if math.isnan(c_price): c_price = 0.0
        except:
            c_price = 0.0
            
        # [V5.25 핵심 복구] S&P 500 달력에 종속되지 않고, 개별 종목 스스로 최근 5일치 일간 차트를 뜯어옴
        try:
            hist = tk_obj.history(period="5d", interval="1d")
            if not hist.empty:
                if hist.index.tz is None: hist.index = hist.index.tz_localize(ny_tz)
                else: hist.index = hist.index.tz_convert(ny_tz)
                
                if len(hist) >= 2:
                    t_close = float(hist['Close'].iloc[-1])
                    d_close = float(hist['Close'].iloc[-2])
                elif len(hist) == 1:
                    t_close = float(hist['Close'].iloc[-1])
                    d_close = t_close
                else:
                    t_close = c_price
                    d_close = c_price
            else:
                t_close, d_close = 0.0, 0.0
        except:
            t_close, d_close = 0.0, 0.0
            
        # 일간 차트 랙 발생 시 비상 캐시데이터 가동
        try:
            prev_c = float(tk_obj.fast_info.previous_close)
            if not math.isnan(prev_c) and t_close == 0.0:
                t_close = prev_c
        except: pass
        
        market_data['STOCKS'][tk] = {'live': c_price, 't_close': t_close, 'd_close': d_close}
        
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

def normalize_category(cat):
    cat_str = str(cat).strip()
    if '코어' in cat_str: return '코어 (Core)'
    if '방어' in cat_str: return '방어 (Defensive)'
    if '우량' in cat_str: return '우량주 (Blue Chip)'
    if '모험' in cat_str: return '모험주 (Adventure)'
    if '모멘텀' in cat_str: return '모멘텀 (Momentum)'
    return '기타 (Others)'

# ==========================================
# 2. 사이드바: 듀얼 컨트롤러 (매매 vs 배당)
# ==========================================
all_us_tickers = get_all_us_tickers()
macro_cache = get_macro_data()

raw_live_fx = macro_cache['USDKRW']['live']
current_live_fx = raw_live_fx if raw_live_fx > 0 else 1350.0

with st.sidebar:
    st.header("⚡ 스마트 트레이딩 룸")
    
    action_mode = st.radio("📝 작업 선택", ["📈 주식 매매 기록", "💰 배당금 수령 기록"], horizontal=True)
    
    if action_mode == "📈 주식 매매 기록":
        st.caption("주식 매수 및 매도 내역을 장부에 추가합니다.")
        with st.form(key='trade_form'):
            t_date = st.date_input("체결 날짜", datetime.date.today())
            selected_option = st.selectbox("🔍 종목 티커/회사명 검색", all_us_tickers)
            t_ticker = st.text_input("티커 직접 입력 (예: RGTI)").upper().strip() if selected_option == "직접 입력 (티커 수동 입력)" else selected_option.split(" | ")[0].strip()
            t_type = st.selectbox("구분", ["매수", "매도"])
            col_qty, col_price = st.columns(2)
            with col_qty: t_qty = st.number_input("체결 수량", value=0.00, min_value=0.00, format="%.4f", step=1.0)
            with col_price: t_price = st.number_input("체결 가격 ($)", value=0.00, min_value=0.00, format="%.2f", step=1.0)
            t_fx = st.number_input("체결 환율 (원)", value=float(current_live_fx), min_value=0.00, format="%.2f", step=1.0)
            t_group = st.selectbox("🧩 자산군 그룹 지정", ["코어 (Core)", "방어 (Defensive)", "우량주 (Blue Chip)", "모험주 (Adventure)", "모멘텀 (Momentum)", "기타 (Others)"])
            
            if st.form_submit_button(label="장부에 즉시 기록"):
                if t_ticker and t_qty > 0 and t_price > 0:
                    current_trade_hash = f"{t_date}_{t_ticker}_{t_type}_{t_qty}_{t_price}"
                    if current_trade_hash == st.session_state['last_trade_hash']:
                        st.warning("⚠️ 중복 클릭이 감지되었습니다.")
                    else:
                        with st.spinner("구글 시트 연동 중..."):
                            if add_trade(t_date, t_ticker, t_type, t_qty, t_price, t_fx, t_group):
                                st.session_state['last_trade_hash'] = current_trade_hash
                                st.success(f"[{t_ticker}] 매매 기록 완료!")
                                load_data.clear(); fetch_market_data.clear()
                                st.rerun()
                            else: st.error("기록 실패.")
                else: st.warning("수량과 가격을 정확히 입력하세요.")
                
    else:
        st.caption("세금이 공제된 실제 입금액(세후 배당금)을 입력하세요.")
        with st.form(key='dividend_form'):
            d_date = st.date_input("입금 날짜", datetime.date.today())
            selected_option = st.selectbox("🔍 배당금 지급 종목", all_us_tickers)
            d_ticker = st.text_input("티커 직접 입력 (예: KO)").upper().strip() if selected_option == "직접 입력 (티커 수동 입력)" else selected_option.split(" | ")[0].strip()
            d_amount = st.number_input("세후 입금액 ($)", value=0.00, min_value=0.00, format="%.2f", step=1.0)
            d_fx = st.number_input("입금 당시 환율 (원)", value=float(current_live_fx), min_value=0.00, format="%.2f", step=1.0)
            
            if st.form_submit_button(label="배당금 장부에 추가"):
                if d_ticker and d_amount > 0:
                    current_div_hash = f"{d_date}_{d_ticker}_배당_{d_amount}"
                    if current_div_hash == st.session_state['last_trade_hash']:
                        st.warning("⚠️ 중복 클릭이 감지되었습니다.")
                    else:
                        with st.spinner("구글 시트 연동 중..."):
                            if add_trade(d_date, d_ticker, "배당", 0.0, d_amount, d_fx, "배당기록"):
                                st.session_state['last_trade_hash'] = current_div_hash
                                st.success(f"[{d_ticker}] 배당금 ${d_amount:.2f} 기록 완료!")
                                load_data.clear(); fetch_market_data.clear()
                                st.rerun()
                            else: st.error("기록 실패.")
                else: st.warning("입금액을 확인하세요.")

# ==========================================
# 3. 프론트엔드 대시보드 렌더링
# ==========================================
try:
    df_trades = load_data()
except Exception:
    st.error("🚨 **[구글 서버 통신 지연]** 구글 시트 장부를 불러오는 중 응답이 없습니다. 잠시 후 새로고침을 눌러주세요.")
    st.stop()

if df_trades.empty:
    st.warning("장부 데이터가 비어있습니다. 사이드바에서 매매/배당 기록을 추가해주세요.")
else:
    group_map = {'VOO': '코어 (Core)', 'SGOV': '코어 (Core)', 'KO': '방어 (Defensive)', 'BAC': '방어 (Defensive)', 'NEE': '방어 (Defensive)', 'LMT': '방어 (Defensive)', 'IBM': '우량주 (Blue Chip)', 'SPCX': '우량주 (Blue Chip)', 'GOOGL': '우량주 (Blue Chip)', 'RGTI': '모험주 (Adventure)', 'ARQQ': '모험주 (Adventure)', 'LEU': '기타 (Others)'}
    
    if '그룹' in df_trades.columns:
        for _, row in df_trades.iterrows():
            tk = str(row.get('종목', '')).strip().upper()
            grp = str(row.get('그룹', '')).strip()
            if tk and grp and grp != "배당기록": 
                group_map[tk] = normalize_category(grp)
                
    def get_category(ticker): 
        cat = group_map.get(ticker.upper(), '기타 (Others)')
        return normalize_category(cat)

    tab1, tab2 = st.tabs(["💰 내 자산 대시보드", "🌍 매크로 종합 상황판"])
    
    with tab1:
        portfolio = {}
        for _, row in df_trades.iterrows():
            ticker, trade_type = str(row.get('종목', '')).strip().upper(), str(row.get('구분', '')).strip()
            try:
                raw_qty = str(row.get('수량', '0')).replace(',', '').replace('$', '').strip()
                raw_price = str(row.get('가격($)', '0')).replace(',', '').replace('$', '').strip()
                raw_fx_val = str(row.get('환율', '')).replace(',', '').replace('$', '').strip()
                
                qty = float(raw_qty) if raw_qty else 0.0
                price = float(raw_price) if raw_price else 0.0
                fx = float(raw_fx_val) if raw_fx_val else (current_live_fx if current_live_fx > 0 else 1350.0)
            except: continue
            
            if ticker not in portfolio: 
                portfolio[ticker] = {'수량': 0.0, '총투자금USD': 0.0, '총투자금KRW': 0.0, '총배당USD': 0.0, '총배당KRW': 0.0}
            
            if trade_type == '매수':
                portfolio[ticker]['수량'] += qty
                portfolio[ticker]['총투자금USD'] += (qty * price)
                portfolio[ticker]['총투자금KRW'] += (qty * price * fx)
            elif trade_type == '매도' and portfolio[ticker]['수량'] > 0:
                avg_usd = portfolio[ticker]['총투자금USD'] / portfolio[ticker]['수량']
                avg_krw = portfolio[ticker]['총투자금KRW'] / portfolio[ticker]['수량']
                portfolio[ticker]['수량'] -= qty
                portfolio[ticker]['총투자금USD'] -= (qty * avg_usd)
                portfolio[ticker]['총투자금KRW'] -= (qty * avg_krw)
            elif trade_type == '배당':
                portfolio[ticker]['총배당USD'] += price
                portfolio[ticker]['총배당KRW'] += (price * fx)

        portfolio = {k: v for k, v in portfolio.items() if (v['수량'] > 0.0001 or v['총배당USD'] > 0)}
        tickers_tuple = tuple(portfolio.keys())
        
        with st.spinner('초경량 무결점 엔진 가동 중...'):
            fetched_data = fetch_market_data(tickers_tuple)
            sp_hist = fetched_data['SP500_hist']
            last_trade_time = fetched_data['LAST_TRADE_TIME']
            
            total_value_usd, total_invested_usd, total_daily_change_usd, total_fx_gain_loss_krw = 0.0, 0.0, 0.0, 0.0
            total_dividend_usd_all = sum(v['총배당USD'] for v in portfolio.values())
            total_dividend_krw_all = sum(v['총배당KRW'] for v in portfolio.values())
            
            results, yesterday_recap, error_tickers = [], [], []
            
            ny_tz = pytz.timezone('America/New_York')
            now_kr = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
            now_ny = datetime.datetime.now(ny_tz)
            
            t_val = now_ny.hour + now_ny.minute / 60.0
            wd = now_ny.weekday() 
            
            is_early_closed = False
            if last_trade_time:
                time_diff = (now_ny - last_trade_time).total_seconds() / 60.0
                if 9.5 <= t_val < 16.0 and time_diff > 30.0:
                    is_early_closed = True

            is_weekend = False
            if wd == 5: is_weekend = True
            elif wd == 4 and t_val >= 20.0: is_weekend = True
            elif wd == 6 and t_val < 20.0: is_weekend = True

            is_today_in_data = now_ny.date() in (sp_hist.index.date.tolist() if not sp_hist.empty else [])
            is_holiday = False
            if 0 <= wd <= 4 and t_val >= 10.0 and not is_today_in_data and not sp_hist.empty:
                is_holiday = True

            if is_weekend:
                m_state, price_basis_label, is_market_closed = "⚫ 주말 (애프터 마감가)", "애프터 마켓 최종가", True
                change_label, short_label = "직전 애프터 누적", "직전 애프터"
            else:
                if is_holiday:
                    m_state, price_basis_label, is_market_closed = "⚫ 미국증시 휴장일 (공휴일)", "전일 마감가", True
                    change_label, short_label = "오늘의 변동-휴장", "휴장"
                elif is_early_closed:
                    m_state, price_basis_label, is_market_closed = "⚠️ 조기 폐장 또는 통신 지연 감지", "조기 마감가 유지", True
                    change_label, short_label = "오늘의 변동-조기 폐장", "조기 폐장"
                else:
                    if t_val >= 20.0 or t_val < 4.0: 
                        m_state, price_basis_label, is_market_closed = "⚪ 데이마켓 (API 가격 멈춤)", "전일 애프터 최종가", False
                        change_label, short_label = "직전 애프터 누적", "직전 애프터"
                    elif 4.0 <= t_val < 9.5: 
                        m_state, price_basis_label, is_market_closed = "🟡 프리마켓 진행 (실시간 변동)", "실시간 프리마켓가", False
                        change_label, short_label = "오늘의 변동-프리마켓", "프리마켓"
                    elif 9.5 <= t_val < 16.0: 
                        m_state, price_basis_label, is_market_closed = "🟢 본장 진행 중", "실시간 본장가", False
                        change_label, short_label = "오늘의 변동-본장", "본장"
                    elif 16.0 <= t_val < 20.0: 
                        m_state, price_basis_label, is_market_closed = "🔵 애프터 마켓 진행 중", "실시간 애프터 마켓가", False
                        change_label, short_label = "오늘의 변동-애프터 마켓", "애프터 마켓"
            
            market_time_info = f"🕒 **조회 시점:** {now_kr.strftime('%Y년 %m월 %d일 %H:%M')} (KST)\n\n**시장 상태:** {m_state}"

            sp500_change = 0.0
            if len(sp_hist) >= 2:
                g_target = float(sp_hist['Close'].iloc[-1])
                g_prev = float(sp_hist['Close'].iloc[-2])
                if g_prev > 0: sp500_change = ((g_target - g_prev) / g_prev) * 100

            for ticker, info in portfolio.items():
                shares = float(info['수량'])
                avg_usd = float(info['총투자금USD']) / shares if shares > 0 else 0
                avg_fx = float(info['총투자금KRW']) / float(info['총투자금USD']) if info['총투자금USD'] > 0 else current_live_fx
                category, kor_name = get_category(ticker), KOR_NAMES.get(ticker, ticker)
                
                stock_data = fetched_data['STOCKS'].get(ticker, {'live': 0.0, 't_close': 0.0, 'd_close': 0.0})
                c_price = stock_data['live']
                t_close = stock_data['t_close']
                d_close = stock_data['d_close']
                
                if is_market_closed and t_close > 0: c_price = t_close
                if c_price == 0.0 or t_close == 0.0:
                    if shares > 0: error_tickers.append(ticker)
                
                # 전일장 마감 요약 로직: 최근 두 종가의 차이 (시간 루프 방지용 절대 기준)
                y_change = ((t_close - d_close) / d_close) * 100 if d_close > 0 else 0.0
                if t_close > 0 and d_close > 0 and shares > 0 and t_close != d_close:
                    yesterday_recap.append({
                        "종목": kor_name, "그룹": category, "어제변동률": y_change,
                        "어제가치": t_close * shares, "그제가치": d_close * shares,
                        "변동액": (t_close - d_close) * shares
                    })
                
                value_usd = c_price * shares
                change_dollar = (c_price - t_close) * shares if t_close > 0 else 0.0
                
                return_percent = ((c_price - avg_usd) / avg_usd) * 100 if avg_usd > 0 else 0.0
                div_usd = float(info['총배당USD'])
                tr_percent = (((value_usd + div_usd) - float(info['총투자금USD'])) / float(info['총투자금USD'])) * 100 if float(info['총투자금USD']) > 0 else 0.0
                daily_percent = ((c_price - t_close) / t_close) * 100 if t_close > 0 else 0.0
                
                stock_fx_gain = 0.0
                div_fx_gain = 0.0
                if current_live_fx > 0:
                    if shares > 0 and info['총투자금USD'] > 0:
                        stock_fx_gain = info['총투자금USD'] * (current_live_fx - avg_fx)
                    if div_usd > 0:
                        div_fx_gain = (div_usd * current_live_fx) - float(info['총배당KRW'])
                
                total_item_fx_gain = stock_fx_gain + div_fx_gain
                
                total_value_usd += value_usd
                total_daily_change_usd += change_dollar
                total_invested_usd += float(info['총투자금USD'])
                total_fx_gain_loss_krw += total_item_fx_gain
                
                if shares > 0 or div_usd > 0:
                    results.append({
                        "티커": ticker, "종목명": kor_name, "그룹": category, "보유 수량": shares,
                        "평단가 ($)": round(avg_usd, 2), "현재가 ($)": round(c_price, 2),
                        "매입환율": round(avg_fx, 2), "누적배당($)": round(div_usd, 2),
                        "주가수익(%)": round(return_percent, 2), "총수익률(TR%)": round(tr_percent, 2),
                        "당일 변동 (%)": round(daily_percent, 2), "환차손익(KRW)": int(total_item_fx_gain),
                        "평가액 ($)": round(value_usd, 2)
                    })

            for row in results: row["비중"] = (row["평가액 ($)"] / total_value_usd) * 100 if total_value_usd > 0 else 0.0
            
            total_profit_usd_only = total_value_usd - total_invested_usd
            total_all_time_usd_tr = ((total_value_usd + total_dividend_usd_all - total_invested_usd) / total_invested_usd) * 100 if total_invested_usd > 0 else 0.0
            
            total_value_krw = total_value_usd * current_live_fx if current_live_fx > 0 else 0.0
            total_invested_krw = sum(portfolio[tk]['총투자금KRW'] for tk in portfolio)
            
            total_dividend_current_krw = total_dividend_usd_all * current_live_fx if current_live_fx > 0 else 0.0
            total_profit_krw_tr = (total_value_krw + total_dividend_current_krw) - total_invested_krw if current_live_fx > 0 else 0.0
            total_return_krw_tr = (total_profit_krw_tr / total_invested_krw) * 100 if (total_invested_krw > 0 and current_live_fx > 0) else 0.0

            st.info(market_time_info)
            if current_live_fx == 0.0: st.error("🚨 **[환율 데이터 오류]** 실시간 환율 수신 불가.")
            if error_tickers: st.error(f"🚨 **[데이터 수신 오류]** 일시적인 야후 서버 지연으로 데이터가 누락되었습니다: **{', '.join(set(error_tickers))}**\n*(5분 뒤 새로고침을 누르세요)*")
            
            st.subheader("💰 계좌 총괄 요약 (Total Summary)")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric(label=f"평가액(USD)-[{price_basis_label}]", value=f"${total_value_usd:,.2f}", delta=f"{total_daily_change_usd:,.2f} USD ({change_label})")
            col2.metric(label="누적 배당금(USD)", value=f"${total_dividend_usd_all:,.2f}", delta="현금흐름 확보", delta_color="normal")
            col3.metric(label="총수익률(TR USD)", value=f"{total_all_time_usd_tr:+.2f}%", delta=f"{(total_profit_usd_only + total_dividend_usd_all):,.2f} USD (손익+배당)")
            col4.metric(label="총수익률(TR KRW)", value=f"{total_return_krw_tr:+.2f}%", delta=f"{int(total_profit_krw_tr):,} 원 (주식+배당+환차)")
            col5.metric(label="평가액(KRW)", value=f"{int(total_value_krw):,} 원", delta=f"총 환차손익: {int(total_fx_gain_loss_krw):,} 원", delta_color="normal")
            st.divider()
            
            if results:
                df = pd.DataFrame(results).sort_values(by="비중", ascending=False).reset_index(drop=True)
                st.subheader("📊 포트폴리오 상세 (주식 성과 및 누적 배당 분리)")
                fig = px.pie(df, values='평가액 ($)', names='그룹', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(df, use_container_width=True, hide_index=True,
                             column_config={"티커": "티커", "종목명": "종목명", "그룹": "자산군", 
                                            "보유 수량": st.column_config.NumberColumn("수량", format="%.4f"),
                                            "평단가 ($)": st.column_config.NumberColumn("평단가($)", format="$%.2f"),
                                            "현재가 ($)": st.column_config.NumberColumn("현재가($)", format="$%.2f"),
                                            "매입환율": st.column_config.NumberColumn("매입환율", format="%.2f"),
                                            "누적배당($)": st.column_config.NumberColumn("누적배당($)", format="$%.2f"),
                                            "주가수익(%)": st.column_config.NumberColumn("단순주가(%)", format="%.2f%%"),
                                            "총수익률(TR%)": st.column_config.NumberColumn("총수익률(TR%)", format="%.2f%%"),
                                            "당일 변동 (%)": st.column_config.NumberColumn(f"{short_label} 변동(%)", format="%.2f%%"),
                                            "평가액 ($)": st.column_config.NumberColumn("평가액($)", format="$%.2f"),
                                            "비중": st.column_config.ProgressColumn("비중(%)", format="%.2f%%", min_value=0, max_value=100)})
                st.divider()
                
                st.header("📰 시황 분석 리포트 (투트랙)")
                st.subheader(f"🌙 1. 최근 정규장 마감 요약")
                if yesterday_recap:
                    df_y = pd.DataFrame(yesterday_recap)
                    tot_dby, tot_y = df_y['그제가치'].sum(), df_y['어제가치'].sum()
                    tot_chg_pct = ((tot_y - tot_dby) / tot_dby * 100) if tot_dby > 0 else 0.0
                    outperform = tot_chg_pct - sp500_change
                    st.markdown(f"**📌 계좌 총괄 성적:** 전일 대비 **{get_color_text(tot_chg_pct)}** ({get_color_text(tot_y - tot_dby, False)})")
                    st.write(f"👉 시장(S&P 500: {get_color_text(sp500_change)}) 대비 **{abs(outperform):.2f}%p {'상회' if outperform > 0 else '하회'}**")
                    
                    st.write("---")
                    st.markdown("**🏆 포트폴리오 양극단 특징주**")
                    valid_df_y = df_y.dropna(subset=['어제변동률'])
                    if not valid_df_y.empty:
                        top, btm = valid_df_y.loc[valid_df_y['어제변동률'].idxmax()], valid_df_y.loc[valid_df_y['어제변동률'].idxmin()]
                        c1, c2 = st.columns(2)
                        with c1: st.success(f"🚀 **최고 효자:** {top['종목']} ({get_color_text(top['어제변동률'])})")
                        with c2: st.error(f"📉 **최대 구멍:** {btm['종목']} ({get_color_text(btm['어제변동률'])})")
                
                st.write("") 
                st.subheader("⚡ 2. 실시간 흐름 파악 (당일 라이브)")
                if is_market_closed or m_state.startswith("⚪"): 
                    st.info("💡 프리마켓 개장 전이므로 실시간 급변동 감지가 비활성화됩니다.")
                else:
                    active_df = df[df['당일 변동 (%)'] != 0.0]
                    if len(active_df) > 0:
                        top_mover = active_df.loc[active_df['당일 변동 (%)'].abs().idxmax()]
                        if abs(top_mover['당일 변동 (%)']) >= 3.0:
                            st.error(f"🚨 **[특징주 감지]** 현재 **{top_mover['종목명']}({top_mover['티커']})** 종목이 **{get_color_text(top_mover['당일 변동 (%)'])}** 급변동 중입니다.")
                            
                            prompt_text = (
                                f"[{now_kr.strftime('%Y년 %m월 %d일 %H:%M')} KST 기준]\n"
                                f"내 포트폴리오의 [{top_mover['티커']}] 종목이 {top_mover['당일 변동 (%)']:+.2f}% 급변동 중이다.\n"
                                f"외신 및 공시를 기반으로 원인과 대응책을 분석하되, 반드시 다음 프로세스를 거쳐서 답변해라:\n"
                                f"1단계: 실시간 가격 확인\n"
                                f"2단계: 뉴스 매칭\n"
                                f"3단계: 정합성 검증"
                            )
                            st.code(prompt_text, language="markdown")
                        else: 
                            st.success("✔️ 기준치(±3%)를 초과하는 실시간 급변동 종목이 없습니다.")

    with tab2:
        st.subheader("🌍 매크로 경제 지표 종합 대시보드")
        st.markdown("### 1. S&P 500 섹터 히트맵")
        components.html('''<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>{"exchanges": [],"dataSource": "SPX500","grouping": "sector","blockSize": "market_cap_basic","blockColor": "change","locale": "kr","colorTheme": "light","hasTopBar": false,"isDataSetEnabled": false,"isZoomEnabled": true,"hasSymbolTooltip": true,"width": "100%","height": "500"}</script></div>''', height=500)
        st.divider()
        st.markdown("### 2. 핵심 매크로 지표 (실시간 숫자 뷰)")
        krw, tnx, wti = macro_cache['USDKRW'], macro_cache['TNX'], macro_cache['WTI']
        
        mac1, mac2, mac3 = st.columns(3)
        with mac1:
            with st.container(border=True):
                st.markdown("**🇺🇸 USD/KRW 환율**")
                st.markdown(f"### {krw['live']:,.2f} 원")
                st.markdown(f"**전일 대비: {get_macro_color_text(krw['change'], False, suffix='원')} ({get_macro_color_text(krw['pct'], True)})**")
        with mac2:
            with st.container(border=True):
                st.markdown("**미국 10년물 국채 금리**")
                st.markdown(f"### {tnx['live']:.3f} %")
                st.markdown(f"**전일 대비: {get_macro_color_text(tnx['change'], False, suffix='%p')} ({get_macro_color_text(tnx['pct'], True)})**")
        with mac3:
            with st.container(border=True):
                st.markdown("**🛢️ WTI 원유 (선물)**")
                st.markdown(f"### ${wti['live']:.2f}")
                st.markdown(f"**전일 대비: {get_macro_color_text(wti['change'], False, prefix='$')} ({get_macro_color_text(wti['pct'], True)})**")
        st.divider()
        
        st.markdown("### 3. 시장 심리 및 금리 예측 지표")
        st.markdown("👉 **[🔗 CNN Fear & Greed Index 실시간 확인하기 (클릭)](https://edition.cnn.com/markets/fear-and-greed)**")
        st.markdown("👉 **[🔗 CME FedWatch Tool (금리 인상 확률) 확인하기 (클릭)](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)**")

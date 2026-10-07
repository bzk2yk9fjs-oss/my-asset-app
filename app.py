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
st.write("V6.1: V5.26 디테일 100% 롤백 + 최하단 찐 투자 성과표(환전 Lock-in) 완벽 통합본")

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

def normalize_category(cat):
    cat_str = str(cat).strip()
    if '코어' in cat_str: return '코어 (Core)'
    if '방어' in cat_str: return '방어 (Defensive)'
    if '우량' in cat_str: return '우량주 (Blue Chip)'
    if '모험' in cat_str: return '모험주 (Adventure)'
    if '모멘텀' in cat_str: return '모멘텀 (Momentum)'
    return '기타 (Others)'

# ==========================================
# 2. 사이드바: 3-Way 통합 컨트롤러
# ==========================================
all_us_tickers = get_all_us_tickers()
macro_cache = get_macro_data()

raw_live_fx = macro_cache['USDKRW']['live']
current_live_fx = raw_live_fx if raw_live_fx > 0 else 1350.0

with st.sidebar:
    st.header("⚡ 스마트 트레이딩 룸")
    
    action_mode = st.radio("📝 작업 선택", ["📈 주식 매매 기록", "💰 배당금 수령 기록", "💵 환전/입출금 기록"], horizontal=True)
    
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
                
    elif action_mode == "💰 배당금 수령 기록":
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
                
    elif action_mode == "💵 환전/입출금 기록":
        st.caption("➕입금(원화->달러 증가) / ➖출금(달러->원화 및 환차익 Lock-in)")
        with st.form(key='fx_form'):
            fx_date = st.date_input("날짜", datetime.date.today())
            fx_type = st.selectbox("거래 분류", ["달러 입금", "달러 출금"])
            fx_usd_amount = st.number_input("달러 금액 ($)", value=0.00, min_value=0.00, format="%.2f", step=10.0)
            fx_rate = st.number_input("적용 환율 (원)", value=float(current_live_fx), min_value=0.00, format="%.2f", step=1.0)
            
            if st.form_submit_button(label="환전 기록 추가"):
                if fx_usd_amount > 0 and fx_rate > 0:
                    current_fx_hash = f"{fx_date}_{fx_type}_{fx_usd_amount}_{fx_rate}"
                    if current_fx_hash == st.session_state['last_trade_hash']:
                        st.warning("⚠️ 중복 클릭이 감지되었습니다.")
                    else:
                        with st.spinner("구글 시트 연동 중..."):
                            if add_trade(fx_date, "USD", fx_type, 0.0, fx_usd_amount, fx_rate, "환전기록"):
                                st.session_state['last_trade_hash'] = current_fx_hash
                                st.success(f"[{fx_type}] ${fx_usd_amount:,.2f} 기록 완료!")
                                load_data.clear(); fetch_market_data.clear()
                                st.rerun()
                            else: st.error("기록 실패.")
                else: st.warning("금액과 환율을 확인하세요.")

# ==========================================
# 3. 프론트엔드 대시보드 렌더링
# ==========================================
df_trades = load_data()

if df_trades.empty:
    st.warning("장부 데이터가 비어있습니다. 사이드바에서 매매/배당 기록을 추가해주세요.")
else:
    # 🚨 버그 수정 완료: 빈 문자열로 덮어씌워져 VOO가 '기타'로 빠지던 현상 차단
    group_map = {'VOO': '코어 (Core)', 'SGOV': '코어 (Core)', 'KO': '방어 (Defensive)', 'BAC': '방어 (Defensive)', 'NEE': '방어 (Defensive)', 'LMT': '방어 (Defensive)', 'IBM': '우량주 (Blue Chip)', 'SPCX': '우량주 (Blue Chip)', 'GOOGL': '우량주 (Blue Chip)', 'RGTI': '모험주 (Adventure)', 'ARQQ': '모험주 (Adventure)', 'LEU': '기타 (Others)'}
    
    if '그룹' in df_trades.columns:
        for _, row in df_trades.iterrows():
            tk = str(row.get('종목', '')).strip().upper()
            grp = str(row.get('그룹', '')).strip()
            # 빈칸 방어 코드 및 환전기록 무시
            if tk and grp and grp not in ["배당기록", "환전기록"]: 
                group_map[tk] = normalize_category(grp)
                
    def get_category(ticker): 
        cat = group_map.get(ticker.upper(), '기타 (Others)')
        return normalize_category(cat)

    tab1, tab2 = st.tabs(["💰 내 자산 대시보드", "🌍 매크로 종합 상황판"])
    
    with tab1:
        # V6.1 락인 회계 변수
        total_deposit_usd = 0.0
        total_withdrawn_usd = 0.0
        lock_in_adjustment = 0.0
        total_buy_usd = 0.0
        total_sold_usd = 0.0
        realized_profit_usd = 0.0
        total_sold_principal_usd = 0.0
        total_sold_principal_krw = 0.0

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
            
            if trade_type == '달러 입금':
                total_deposit_usd += price
                continue
            elif trade_type == '달러 출금':
                total_withdrawn_usd += price
                lock_in_adjustment += (price * fx) - (price * current_live_fx)
                continue
            
            if ticker not in portfolio: 
                portfolio[ticker] = {'수량': 0.0, '총투자금USD': 0.0, '총투자금KRW': 0.0, '총배당USD': 0.0, '총배당KRW': 0.0}
            
            if trade_type == '매수':
                total_buy_usd += (qty * price)
                portfolio[ticker]['수량'] += qty
                portfolio[ticker]['총투자금USD'] += (qty * price)
                portfolio[ticker]['총투자금KRW'] += (qty * price * fx)
            elif trade_type == '매도' and portfolio[ticker]['수량'] > 0:
                total_sold_usd += (qty * price)
                avg_usd = portfolio[ticker]['총투자금USD'] / portfolio[ticker]['수량']
                avg_krw = portfolio[ticker]['총투자금KRW'] / portfolio[ticker]['수량']
                
                total_sold_principal_usd += (qty * avg_usd)
                total_sold_principal_krw += (qty * avg_krw)
                realized_profit_usd += (qty * price) - (qty * avg_usd)

                portfolio[ticker]['수량'] -= qty
                portfolio[ticker]['총투자금USD'] -= (qty * avg_usd)
                portfolio[ticker]['총투자금KRW'] -= (qty * avg_krw)
            elif trade_type == '배당':
                portfolio[ticker]['총배당USD'] += price
                portfolio[ticker]['총배당KRW'] += (price * fx)

        portfolio = {k: v for k, v in portfolio.items() if (v['수량'] > 0.0001 or v['총배당USD'] > 0)}
        tickers_tuple = tuple(portfolio.keys())
        
        total_dividend_usd_all = sum(v['총배당USD'] for v in portfolio.values())
        usd_cash_balance = (total_deposit_usd + total_sold_usd + total_dividend_usd_all) - (total_buy_usd + total_withdrawn_usd)

        with st.spinner('V4.14 정밀 타격 엔진 가동 중...'):
            fetched_data = fetch_market_data(tickers_tuple)
            trading_dates = fetched_data['trading_dates']
            sp500_reg = fetched_data['sp500_reg']
            
            total_value_usd, total_invested_usd = 0.0, 0.0
            total_daily_change_usd = 0.0
            total_fx_gain_loss_krw = 0.0
            
            results = []
            yesterday_recap = []
            error_tickers = []
            
            ny_tz = pytz.timezone('America/New_York')
            now_kr = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
            now_ny = datetime.datetime.now(ny_tz)
            
            if now_ny.time() >= datetime.time(16, 0):
                valid_dates = [d for d in trading_dates if d <= now_ny.date()]
            else:
                valid_dates = [d for d in trading_dates if d < now_ny.date()]
                
            if len(valid_dates) >= 2:
                target_date = valid_dates[-1]
                prev_target_date = valid_dates[-2]
                last_closed_date_str = target_date.strftime('%m/%d')
            else:
                target_date = now_ny.date()
                prev_target_date = target_date - datetime.timedelta(days=1)
                last_closed_date_str = target_date.strftime('%m/%d')

            t_val = now_ny.hour + now_ny.minute / 60.0
            is_market_closed = False
            
            if now_ny.weekday() >= 5: 
                m_state = "⚫ 주말 (애프터 마켓 최종 마감 가격 유지)"
                price_basis_label = "애프터 마켓 최종 마감가"
                change_label = "직전 애프터 누적"
                is_market_closed = True
            elif 4.0 <= t_val < 9.5:
                m_state = "🟡 프리마켓 진행 중"
                price_basis_label = "실시간 프리마켓 가격"
                change_label = "오늘의 변동-프리마켓"
            elif 9.5 <= t_val < 16.0:
                m_state = "🟢 본장 진행 중"
                price_basis_label = "실시간 본장 가격"
                change_label = "오늘의 변동-본장"
            elif 16.0 <= t_val < 20.0:
                m_state = "🔵 애프터 마켓 진행 중"
                price_basis_label = "실시간 애프터 마켓 가격"
                change_label = "오늘의 변동-애프터 마켓"
            else:
                m_state = "⚫ 애프터 마감 (프리마켓 개장 전)"
                price_basis_label = "애프터 마켓 최종 마감가"
                change_label = "직전 애프터 누적"
                is_market_closed = True
                
            market_time_info = f"🕒 **조회 시점:** {now_kr.strftime('%Y년 %m월 %d일 %H:%M')} (KST)\n\n**시장 상태:** {m_state}"

            for ticker, info in portfolio.items():
                shares = float(info['수량'])
                avg_usd_price = float(info['총투자금USD']) / shares if shares > 0 else 0
                avg_purchase_fx = float(info['총투자금KRW']) / float(info['총투자금USD']) if info['총투자금USD'] > 0 else current_live_fx
                category = get_category(ticker)
                kor_name = KOR_NAMES.get(ticker, ticker)
                
                stock_data = fetched_data['STOCKS'].get(ticker, {'df_1d': pd.DataFrame(), 'df_5m': pd.DataFrame()})
                df_1d = stock_data['df_1d']
                df_5m = stock_data['df_5m']
                
                if not df_5m.empty:
                    df_5m_reg = df_5m.between_time('09:30', '16:00')
                else:
                    df_5m_reg = pd.DataFrame()
                    
                def get_exact_close(d_target):
                    if not df_1d.empty and 'date' in df_1d.columns:
                        match_1d = df_1d[df_1d['date'] == d_target]
                        if not match_1d.empty and pd.notna(match_1d['Close'].iloc[-1]):
                            return float(match_1d['Close'].iloc[-1])
                    if not df_5m_reg.empty:
                        match_5m = df_5m_reg[df_5m_reg.index.date == d_target]
                        if not match_5m.empty and pd.notna(match_5m['Close'].iloc[-1]):
                            return float(match_5m['Close'].iloc[-1])
                    return 0.0

                t_close = get_exact_close(target_date)
                d_close = get_exact_close(prev_target_date)
                
                if not df_5m.empty:
                    valid_live = df_5m.dropna(subset=['Close'])
                    c_price = float(valid_live['Close'].iloc[-1]) if not valid_live.empty else t_close
                else:
                    c_price = t_close
                    
                if c_price == 0.0 or t_close == 0.0:
                    if shares > 0: error_tickers.append(ticker)
                    continue

                y_change = ((t_close - d_close) / d_close) * 100 if d_close > 0 else 0.0
                y_value = t_close * shares
                dby_value = d_close * shares
                
                if shares > 0 and t_close != d_close:
                    yesterday_recap.append({
                        "종목": kor_name, "그룹": category, "어제변동률": y_change,
                        "어제가치": y_value, "그제가치": dby_value, "변동액": y_value - dby_value
                    })
                
                value_usd = c_price * shares
                change_dollar = (c_price - t_close) * shares if t_close > 0 else 0.0
                
                return_percent = ((c_price - avg_usd_price) / avg_usd_price) * 100 if avg_usd_price > 0 else 0.0
                daily_percent = ((c_price - t_close) / t_close) * 100 if t_close > 0 else 0.0
                
                div_usd = float(info['총배당USD'])
                
                stock_fx_gain = 0.0
                div_fx_gain = 0.0
                if current_live_fx > 0:
                    if shares > 0 and info['총투자금USD'] > 0:
                        stock_fx_gain = info['총투자금USD'] * (current_live_fx - avg_purchase_fx)
                    if div_usd > 0:
                        div_fx_gain = (div_usd * current_live_fx) - float(info['총배당KRW'])
                
                total_item_fx_gain = stock_fx_gain + div_fx_gain
                
                total_value_usd += value_usd
                total_daily_change_usd += change_dollar
                total_invested_usd += float(info['총투자금USD'])
                total_fx_gain_loss_krw += total_item_fx_gain
                
                # 🚨 버그 수정 완료: V5.26 오리지널 딕셔너리 구조 100% 롤백
                if shares > 0 or div_usd > 0:
                    results.append({
                        "티커": ticker, "종목명": kor_name, "그룹": category, "보유 수량": shares,
                        "평단가 ($)": round(avg_usd_price, 2), "현재가 ($)": round(c_price, 2),
                        "매입환율": round(avg_purchase_fx, 2), "누적배당($)": round(div_usd, 2),
                        "주가수익(%)": round(return_percent, 2),
                        "당일 변동 (%)": round(daily_percent, 2), "환차손익(KRW)": int(total_item_fx_gain),
                        "평가액 ($)": round(value_usd, 2)
                    })

            def get_sp500_close(d_target):
                if not sp500_reg.empty:
                    match_5m = sp500_reg[sp500_reg.index.date == d_target]
                    if not match_5m.empty and pd.notna(match_5m['Close'].iloc[-1]):
                        return float(match_5m['Close'].iloc[-1])
                return 0.0
                
            g_target = get_sp500_close(target_date)
            g_prev = get_sp500_close(prev_target_date)
            sp500_change = ((g_target - g_prev) / g_prev) * 100 if g_prev > 0 else 0.0

            for row in results: row["비중"] = (row["평가액 ($)"] / total_value_usd) * 100 if total_value_usd > 0 else 0.0
            
            total_profit_usd_only = total_value_usd - total_invested_usd
            total_all_time_usd_tr = ((total_value_usd + total_dividend_usd_all - total_invested_usd) / total_invested_usd) * 100 if total_invested_usd > 0 else 0.0
            
            total_value_krw = total_value_usd * current_live_fx if current_live_fx > 0 else 0.0
            total_invested_krw = sum(portfolio[tk]['총투자금KRW'] for tk in portfolio)
            
            total_dividend_current_krw = total_dividend_usd_all * current_live_fx if current_live_fx > 0 else 0.0
            total_profit_krw_tr = (total_value_krw + total_dividend_current_krw) - total_invested_krw if current_live_fx > 0 else 0.0
            total_return_krw_tr = (total_profit_krw_tr / total_invested_krw) * 100 if (total_invested_krw > 0 and current_live_fx > 0) else 0.0

            # 🚨 버그 수정 완료: 상태 정보 및 에러 출력 복구
            st.info(market_time_info)
            if current_live_fx == 0.0: st.error("🚨 **[환율 데이터 오류]** 실시간 환율 수신 불가.")
            if error_tickers: st.error(f"🚨 **[데이터 수신 오류]** 일시적인 야후 서버 지연으로 데이터 누락: **{', '.join(set(error_tickers))}**")
            
            # 🚨 버그 수정 완료: V5.26 델타 텍스트 및 레이아웃 100% 롤백
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
                
                # 🚨 버그 수정 완료: V5.26 전용 데이터프레임 컬럼 포맷팅 완벽 롤백
                st.dataframe(df, use_container_width=True, hide_index=True,
                             column_config={"티커": "티커", "종목명": "종목명", "그룹": "자산군", 
                                            "보유 수량": st.column_config.NumberColumn("수량", format="%.4f"),
                                            "평단가 ($)": st.column_config.NumberColumn("평단가($)", format="$%.2f"),
                                            "현재가 ($)": st.column_config.NumberColumn("현재가($)", format="$%.2f"),
                                            "매입환율": st.column_config.NumberColumn("매입환율", format="%.2f"),
                                            "누적배당($)": st.column_config.NumberColumn("누적배당($)", format="$%.2f"),
                                            "주가수익(%)": st.column_config.NumberColumn("단순주가(%)", format="%.2f%%"),
                                            "당일 변동 (%)": st.column_config.NumberColumn("당일변동(%)", format="%.2f%%"),
                                            "환차손익(KRW)": st.column_config.NumberColumn("환차손익(원)"),
                                            "평가액 ($)": st.column_config.NumberColumn("평가액($)", format="$%.2f"),
                                            "비중": st.column_config.ProgressColumn("비중(%)", format="%.2f%%", min_value=0, max_value=100)})
                st.divider()
                
                st.header("📰 시황 분석 리포트 (투트랙)")
                st.subheader(f"🌙 1. 전일장 마감 요약 (미국시간 {last_closed_date_str} 정규장 마감 기준)")
                if yesterday_recap:
                    df_y = pd.DataFrame(yesterday_recap)
                    tot_dby = df_y['그제가치'].sum()
                    tot_y = df_y['어제가치'].sum()
                    tot_chg_dollar = tot_y - tot_dby
                    tot_chg_pct = (tot_chg_dollar / tot_dby * 100) if tot_dby > 0 else 0.0
                    outperform = tot_chg_pct - sp500_change
                    
                    st.markdown(f"**📌 계좌 총괄 성적:** 전일 대비 **{get_color_text(tot_chg_pct)}** ({get_color_text(tot_chg_dollar, False)})")
                    st.write(f"👉 시장(S&P 500: {get_color_text(sp500_change)}) 대비 **{abs(outperform):.2f}%p {'상회' if outperform > 0 else '하회'}**")
                    
                    st.write("---")
                    st.markdown("**🧩 섹터/그룹별 기여도**")
                    group_totals_y = df_y.groupby('그룹')['어제가치'].sum()
                    group_totals_dby = df_y.groupby('그룹')['그제가치'].sum()
                    group_pcts = []
                    for g in group_totals_dby.index:
                        if group_totals_dby[g] > 0:
                            g_pct = ((group_totals_y[g] - group_totals_dby[g]) / group_totals_dby[g]) * 100
                            group_pcts.append(f"{g.split(' ')[0]} {get_color_text(g_pct)}")
                    st.write(" | ".join(group_pcts))

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

            # ---------------------------------------------------------
            # 🚀 최하단: 찐 투자 성과표 (옵션 A - 무결점 락인 패널)
            # ---------------------------------------------------------
            st.divider()
            st.header("⚖️ 최종 회계 결산: 찐 투자 성과표")
            st.caption("환율 변동 리스크가 배제된 실제 주머니 확정 수익(Lock-in)과 순수 달러 잔고를 점검합니다.")
            
            box2_profit_usd = realized_profit_usd + total_dividend_usd_all
            base_realized_krw = (box2_profit_usd * current_live_fx) + (total_sold_principal_usd * current_live_fx - total_sold_principal_krw)
            box3_profit_krw = base_realized_krw + lock_in_adjustment
            
            b1, b2, b3, b4 = st.columns(4)
            with b1: st.metric("[1칸] 누적 수령 배당금(USD)", f"${total_dividend_usd_all:,.2f}", "달러 현금흐름 누적액", delta_color="normal")
            with b2: st.metric("[2칸] 총 누적 손익(USD)", f"${box2_profit_usd:,.2f}", "매도 차익 + 배당금")
            with b3: st.metric("[3칸] 총 누적 손익(KRW)", f"{int(box3_profit_krw):,} 원", "실시간 환차익 + 환전 Lock-in 합산")
            with b4: st.metric("[4칸] 미환전 달러 잔고(USD)", f"${usd_cash_balance:,.2f}", "증권사 예수금과 100% 일치", delta_color="off")

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

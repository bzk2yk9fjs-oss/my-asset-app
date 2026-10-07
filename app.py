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

# ==========================================
# 0. 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="한결 퀀트 포트폴리오", layout="wide", page_icon="📈")

st.title("📈 한결 퀀트 & 매크로 자산관리 비서")
st.write("V6.1: 최강 분석 엔진(V5.26) + 옵션 A(달러 예수금 완벽 통제 및 최하단 락인 패널) 단일 통합본")

if 'last_trade_hash' not in st.session_state:
    st.session_state['last_trade_hash'] = None

# ==========================================
# 1. 네트워크 및 데이터 로드 (V5.26 원본 보존)
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
})
adapter = TimeoutHTTPAdapter(timeout=10)
yf_session.mount("https://", adapter)
yf_session.mount("http://", adapter)

KOR_NAMES = {
    'VOO': '뱅가드 S&P 500', 'SGOV': '미국 0-3개월 초단기채', 'KO': '코카콜라', 
    'BAC': '뱅크오브아메리카', 'NEE': '넥스트에라 에너지', 'LMT': '록히드 마틴', 
    'GOOGL': '알파벳 A', 'IBM': 'IBM', 'SPCX': '스페이스X', 
    'RGTI': '리게티 컴퓨팅', 'ARQQ': '아킷 퀀텀',
    'AAPL': '애플', 'MSFT': '마이크로소프트', 'AMZN': '아마존닷컴', 'NVDA': '엔비디아', 
    'TSLA': '테슬라', 'META': '메타 플랫폼스'
}

def get_color_text(val, is_percent=True):
    if pd.isna(val) or val is None: return ":gray[데이터 없음]"
    sign = "+" if val > 0 else ""
    fmt = f"{val:.2f}"
    res = f"{sign}{fmt}%" if is_percent else f"{sign}${abs(val):.2f}"
    if val > 0: return f":green[{res}]"
    elif val < 0: return f":red[{res}]"
    else: return f":gray[{res}]"

def get_macro_color_text(val, is_percent=True, prefix="", suffix=""):
    if pd.isna(val) or val is None: return ":gray[데이터 없음]"
    sign = "+" if val > 0 else ""
    fmt = f"{val:.2f}"
    res = f"{sign}{fmt}%" if is_percent else f"{sign}{prefix}{abs(val):.2f}{suffix}"
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
    except Exception:
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
            live = float(tk.fast_info.last_price) if not math.isnan(float(tk.fast_info.last_price)) else 0.0
            prev = float(tk.fast_info.previous_close) if not math.isnan(float(tk.fast_info.previous_close)) else 0.0
            if key == "TNX" and live > 10:
                live /= 10; prev /= 10
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
        sp500_5m.index = sp500_5m.index.tz_convert(ny_tz) if sp500_5m.index.tz is not None else sp500_5m.index.tz_localize('UTC').tz_convert(ny_tz)
        sp500_reg = sp500_5m.between_time('09:30', '16:00')
        trading_dates = sorted(list(set(sp500_reg.index.date)))
    else:
        trading_dates, sp500_reg = [], pd.DataFrame()
        
    market_data['trading_dates'] = trading_dates
    market_data['sp500_reg'] = sp500_reg

    for tk in tickers_tuple:
        tk_obj = yf.Ticker(tk, session=yf_session)
        try: df_1d = tk_obj.history(period="15d", interval="1d")
        except: df_1d = pd.DataFrame()
        try: df_5m = tk_obj.history(period="15d", interval="5m", prepost=True)
        except: df_5m = pd.DataFrame()
        
        if not df_1d.empty:
            df_1d.index = df_1d.index.tz_convert(ny_tz) if df_1d.index.tz is not None else df_1d.index.tz_localize(ny_tz)
            df_1d['date'] = df_1d.index.date
        if not df_5m.empty:
            df_5m.index = df_5m.index.tz_convert(ny_tz) if df_5m.index.tz is not None else df_5m.index.tz_localize('UTC').tz_convert(ny_tz)
            
        market_data['STOCKS'][tk] = {'df_1d': df_1d, 'df_5m': df_5m}
    return market_data

def normalize_category(cat):
    cat_str = str(cat).strip()
    if '코어' in cat_str: return '코어 (Core)'
    if '방어' in cat_str: return '방어 (Defensive)'
    if '우량' in cat_str: return '우량주 (Blue Chip)'
    if '모험' in cat_str: return '모험주 (Adventure)'
    if '모멘텀' in cat_str: return '모멘텀 (Momentum)'
    return '기타 (Others)'

all_us_tickers = ["직접 입력 (티커 수동 입력)", "VOO | 뱅가드 S&P 500", "SGOV | 미국 0-3개월 초단기채", "SPCX | 스페이스X"]
macro_cache = get_macro_data()
raw_live_fx = macro_cache['USDKRW']['live']
current_live_fx = raw_live_fx if raw_live_fx > 0 else 1350.0

# ==========================================
# 2. 사이드바: 3-Way 통합 컨트롤러 (환전 관제탑)
# ==========================================
with st.sidebar:
    st.header("⚡ 스마트 트레이딩 룸")
    action_mode = st.radio("📝 작업 선택", ["📈 주식 매매", "💰 배당금", "💵 환전/입출금"], horizontal=True)
    
    if action_mode == "📈 주식 매매":
        with st.form(key='trade_form'):
            t_date = st.date_input("체결 날짜", datetime.date.today())
            selected_option = st.selectbox("🔍 종목 검색", all_us_tickers)
            t_ticker = st.text_input("티커 직접 입력").upper().strip() if "직접 입력" in selected_option else selected_option.split(" | ")[0].strip()
            t_type = st.selectbox("구분", ["매수", "매도"])
            c_qty, c_price = st.columns(2)
            with c_qty: t_qty = st.number_input("수량", min_value=0.00, format="%.4f")
            with c_price: t_price = st.number_input("단가($)", min_value=0.00, format="%.2f")
            t_fx = st.number_input("환율(원)", value=float(current_live_fx), format="%.2f")
            t_group = st.selectbox("자산군 지정", ["코어 (Core)", "방어 (Defensive)", "우량주 (Blue Chip)", "모험주 (Adventure)"])
            
            if st.form_submit_button("장부 기록"):
                if t_ticker and t_qty > 0 and t_price > 0:
                    hash_val = f"{t_date}_{t_ticker}_{t_type}_{t_qty}"
                    if hash_val != st.session_state['last_trade_hash']:
                        if add_trade(t_date, t_ticker, t_type, t_qty, t_price, t_fx, t_group):
                            st.session_state['last_trade_hash'] = hash_val
                            st.success("기록 완료!"); load_data.clear(); fetch_market_data.clear(); st.rerun()
                
    elif action_mode == "💰 배당금":
        with st.form(key='dividend_form'):
            d_date = st.date_input("입금 날짜", datetime.date.today())
            d_ticker = st.text_input("티커").upper().strip()
            d_amount = st.number_input("세후 입금액($)", min_value=0.00, format="%.2f")
            d_fx = st.number_input("환율(원)", value=float(current_live_fx), format="%.2f")
            
            if st.form_submit_button("배당 추가"):
                if d_ticker and d_amount > 0:
                    if add_trade(d_date, d_ticker, "배당", 0.0, d_amount, d_fx, "배당기록"):
                        st.success("배당 기록 완료!"); load_data.clear(); fetch_market_data.clear(); st.rerun()

    elif action_mode == "💵 환전/입출금":
        st.caption("➕달러 입금(예수금 증가) / ➖달러 출금(환차익 Lock-in)")
        with st.form(key='fx_form'):
            fx_date = st.date_input("날짜", datetime.date.today())
            fx_type = st.selectbox("거래 분류", ["달러 입금", "달러 출금"])
            fx_usd = st.number_input("달러 금액($)", min_value=0.00, format="%.2f", step=10.0)
            fx_rate = st.number_input("적용 환율(원)", value=float(current_live_fx), format="%.2f")
            
            if st.form_submit_button("환전 기록"):
                if fx_usd > 0 and fx_rate > 0:
                    if add_trade(fx_date, "USD", fx_type, 0.0, fx_usd, fx_rate, "환전기록"):
                        st.success("환전 기록 완료!"); load_data.clear(); fetch_market_data.clear(); st.rerun()

# ==========================================
# 3. 메인 대시보드 렌더링 (투 탭 구조 & 최하단 성과표)
# ==========================================
df_trades = load_data()

if df_trades.empty:
    st.warning("데이터가 없습니다. 사이드바에서 기록을 추가해주세요.")
else:
    group_map = {'VOO': '코어 (Core)', 'SGOV': '코어 (Core)', 'SPCX': '우량주 (Blue Chip)', 'KO': '방어 (Defensive)', 'RGTI': '모험주 (Adventure)'}
    for _, row in df_trades.iterrows():
        tk = str(row.get('종목', '')).strip().upper()
        grp = str(row.get('그룹', '')).strip()
        if tk and grp not in ["배당기록", "환전기록"]: group_map[tk] = normalize_category(grp)
            
    def get_category(ticker): return normalize_category(group_map.get(ticker.upper(), '기타 (Others)'))

    tab1, tab2 = st.tabs(["💰 내 자산 대시보드", "🌍 매크로 종합 상황판"])
    
    with tab1:
        # [환전 락인 엔진] 변수 선언
        total_deposit_usd, total_withdrawn_usd = 0.0, 0.0
        lock_in_adjustment = 0.0
        total_buy_usd, total_sold_usd = 0.0, 0.0
        realized_profit_usd = 0.0
        total_sold_principal_usd, total_sold_principal_krw = 0.0, 0.0
        
        portfolio = {}
        for _, row in df_trades.iterrows():
            ticker, t_type = str(row.get('종목', '')).strip().upper(), str(row.get('구분', '')).strip()
            try:
                qty = float(str(row.get('수량', '0')).replace(',', '').replace('$', '').strip())
                price = float(str(row.get('가격($)', '0')).replace(',', '').replace('$', '').strip())
                fx = float(str(row.get('환율', '0')).replace(',', '').replace('$', '').strip())
                if fx == 0: fx = current_live_fx
            except: continue
            
            if t_type == '달러 입금': total_deposit_usd += price; continue
            elif t_type == '달러 출금': 
                total_withdrawn_usd += price
                lock_in_adjustment += (price * fx) - (price * current_live_fx) # Lock-in 로직
                continue

            if ticker not in portfolio: portfolio[ticker] = {'수량': 0.0, '투자금USD': 0.0, '투자금KRW': 0.0, '배당USD': 0.0}
            
            if t_type == '매수':
                total_buy_usd += (qty * price)
                portfolio[ticker]['수량'] += qty
                portfolio[ticker]['투자금USD'] += (qty * price)
                portfolio[ticker]['투자금KRW'] += (qty * price * fx)
            elif t_type == '매도' and portfolio[ticker]['수량'] > 0:
                total_sold_usd += (qty * price)
                avg_usd = portfolio[ticker]['투자금USD'] / portfolio[ticker]['수량']
                avg_krw = portfolio[ticker]['투자금KRW'] / portfolio[ticker]['수량']
                total_sold_principal_usd += (qty * avg_usd)
                total_sold_principal_krw += (qty * avg_krw)
                realized_profit_usd += (qty * price) - (qty * avg_usd)
                
                portfolio[ticker]['수량'] -= qty
                portfolio[ticker]['투자금USD'] -= (qty * avg_usd)
                portfolio[ticker]['투자금KRW'] -= (qty * avg_krw)
            elif t_type == '배당':
                portfolio[ticker]['배당USD'] += price

        portfolio = {k: v for k, v in portfolio.items() if (v['수량'] > 0.0001 or v['배당USD'] > 0)}
        total_dividend_usd_all = sum(v['배당USD'] for v in portfolio.values())
        usd_cash_balance = (total_deposit_usd + total_sold_usd + total_dividend_usd_all) - (total_buy_usd + total_withdrawn_usd)
        
        with st.spinner('V5.26 정밀 분석 엔진 가동 중...'):
            fetched = fetch_market_data(tuple(portfolio.keys()))
            trading_dates, sp500_reg = fetched['trading_dates'], fetched['sp500_reg']
            
            total_val_usd, total_inv_usd = 0.0, 0.0
            tot_day_chg_usd, tot_fx_gain_krw = 0.0, 0.0
            results, yesterday_recap, error_tk = [], [], []
            
            group_y_val, group_dby_val = {}, {}
            for grp in ["코어 (Core)", "방어 (Defensive)", "우량주 (Blue Chip)", "모험주 (Adventure)", "모멘텀 (Momentum)", "기타 (Others)"]:
                group_y_val[grp] = 0.0
                group_dby_val[grp] = 0.0
            
            now_ny = datetime.datetime.now(pytz.timezone('America/New_York'))
            valid_dates = [d for d in trading_dates if d <= now_ny.date()] if now_ny.time() >= datetime.time(16, 0) else [d for d in trading_dates if d < now_ny.date()]
            target_date = valid_dates[-1] if len(valid_dates) >= 2 else now_ny.date()
            prev_target_date = valid_dates[-2] if len(valid_dates) >= 2 else target_date - datetime.timedelta(days=1)
            
            for ticker, info in portfolio.items():
                shares, div_usd = info['수량'], info['배당USD']
                avg_usd = info['투자금USD'] / shares if shares > 0 else 0
                avg_fx = info['투자금KRW'] / info['투자금USD'] if info['투자금USD'] > 0 else current_live_fx
                category = get_category(ticker)
                
                df_1d = fetched['STOCKS'].get(ticker, {}).get('df_1d', pd.DataFrame())
                df_5m = fetched['STOCKS'].get(ticker, {}).get('df_5m', pd.DataFrame())
                df_5m_reg = df_5m.between_time('09:30', '16:00') if not df_5m.empty else pd.DataFrame()
                
                def get_close(d_tar):
                    if not df_1d.empty and 'date' in df_1d.columns:
                        m1 = df_1d[df_1d['date'] == d_tar]
                        if not m1.empty and pd.notna(m1['Close'].iloc[-1]): return float(m1['Close'].iloc[-1])
                    if not df_5m_reg.empty:
                        m5 = df_5m_reg[df_5m_reg.index.date == d_tar]
                        if not m5.empty and pd.notna(m5['Close'].iloc[-1]): return float(m5['Close'].iloc[-1])
                    return 0.0

                t_close, d_close = get_close(target_date), get_close(prev_target_date)
                c_price = float(df_5m.dropna(subset=['Close'])['Close'].iloc[-1]) if not df_5m.empty else t_close
                
                if c_price == 0.0 or t_close == 0.0:
                    if shares > 0: error_tk.append(ticker)
                    continue

                y_value, dby_value = t_close * shares, d_close * shares
                if shares > 0 and t_close != d_close:
                    yesterday_recap.append({"종목": KOR_NAMES.get(ticker, ticker), "어제변동률": ((t_close-d_close)/d_close)*100, "어제가치": y_value, "그제가치": dby_value})
                    group_y_val[category] += y_value
                    group_dby_val[category] += dby_value
                
                val_usd = c_price * shares
                tot_item_fx = (info['투자금USD'] * (current_live_fx - avg_fx)) if current_live_fx > 0 and shares > 0 else 0.0
                
                total_val_usd += val_usd
                total_inv_usd += info['투자금USD']
                tot_day_chg_usd += (c_price - t_close) * shares
                tot_fx_gain_krw += tot_item_fx
                
                if shares > 0 or div_usd > 0:
                    results.append({"티커": ticker, "그룹": category, "수량": shares, "평단($)": avg_usd, "현재가($)": c_price, 
                                    "당일(%)": ((c_price-t_close)/t_close)*100 if t_close>0 else 0, "평가액($)": val_usd})

            g_tar = float(sp500_reg[sp500_reg.index.date == target_date]['Close'].iloc[-1]) if not sp500_reg.empty and len(sp500_reg[sp500_reg.index.date == target_date]) > 0 else 0.0
            g_prv = float(sp500_reg[sp500_reg.index.date == prev_target_date]['Close'].iloc[-1]) if not sp500_reg.empty and len(sp500_reg[sp500_reg.index.date == prev_target_date]) > 0 else 0.0
            sp500_change = ((g_tar - g_prv) / g_prv) * 100 if g_prv > 0 else 0.0

            # --- 상단 요약 지표 (Total Summary) ---
            total_inv_krw = sum(portfolio[tk]['투자금KRW'] for tk in portfolio)
            tr_usd_pct = ((total_val_usd + total_dividend_usd_all - total_inv_usd) / total_inv_usd) * 100 if total_inv_usd > 0 else 0.0
            tr_krw_pct = (((total_val_usd * current_live_fx) + (total_dividend_usd_all * current_live_fx) - total_inv_krw) / total_inv_krw) * 100 if total_inv_krw > 0 else 0.0
            total_val_krw = total_val_usd * current_live_fx
            
            st.subheader("💰 계좌 총괄 요약 (Total Summary)")
            r1, r2, r3, r4, r5 = st.columns(5)
            r1.metric("평가액(USD)", f"${total_val_usd:,.2f}", f"{tot_day_chg_usd:,.2f} USD")
            r2.metric("누적 배당금(USD)", f"${total_dividend_usd_all:,.2f}")
            r3.metric("총수익률(TR USD)", f"{tr_usd_pct:+.2f}%")
            r4.metric("총수익률(TR KRW)", f"{tr_krw_pct:+.2f}%")
            r5.metric("평가액(KRW)", f"{int(total_val_krw):,} 원", f"총 환차손익: {int(tot_fx_gain_krw):,} 원")
            
            st.divider()
            
            # --- 포트폴리오 상세 ---
            if results:
                df = pd.DataFrame(results)
                st.subheader("📊 포트폴리오 비중")
                fig = px.pie(df, values='평가액($)', names='그룹', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textinfo='percent+label'); fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0))
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df.sort_values(by="평가액($)", ascending=False), use_container_width=True, hide_index=True)
                
                st.divider()
                
                # --- V5.26 오리지널: 시황 분석 리포트 (투트랙) ---
                st.header("📰 시황 분석 리포트 (투트랙)")
                st.subheader(f"🌙 1. 전일장 마감 요약 ({target_date.strftime('%m/%d')} 정규장 기준)")
                if yesterday_recap:
                    df_y = pd.DataFrame(yesterday_recap)
                    tot_y, tot_dby = df_y['어제가치'].sum(), df_y['그제가치'].sum()
                    tot_chg_pct = ((tot_y - tot_dby) / tot_dby * 100) if tot_dby > 0 else 0.0
                    
                    st.markdown(f"📌 **계좌 총괄 성적:** 전일 대비 {get_color_text(tot_chg_pct)}")
                    st.write(f"👉 시장(S&P 500: {get_color_text(sp500_change)}) 대비 **{abs(tot_chg_pct - sp500_change):.2f}%p {'상회' if (tot_chg_pct - sp500_change)>0 else '하회'}**했습니다.")
                    
                    st.markdown("---")
                    st.markdown("🧩 **섹터/그룹별 기여도**")
                    grp_strs = []
                    for g_name, g_dby in group_dby_val.items():
                        if g_dby > 0:
                            g_chg = ((group_y_val[g_name] - g_dby) / g_dby) * 100
                            grp_strs.append(f"{g_name.split(' ')[0]} {g_chg:+.2f}%")
                    if grp_strs: st.write(" | ".join(grp_strs))
                    
                    st.markdown("---")
                    st.markdown("🏆 **포트폴리오 양극단 특징주**")
                    valid_df_y = df_y.dropna(subset=['어제변동률'])
                    if not valid_df_y.empty:
                        top, btm = valid_df_y.loc[valid_df_y['어제변동률'].idxmax()], valid_df_y.loc[valid_df_y['어제변동률'].idxmin()]
                        c1, c2 = st.columns(2)
                        with c1: st.success(f"🚀 **최고 효자:** {top['종목']} ({get_color_text(top['어제변동률'])})")
                        with c2: st.error(f"📉 **최대 구멍:** {btm['종목']} ({get_color_text(btm['어제변동률'])})")
                
                st.write("")
                st.subheader("⚡ 2. 실시간 흐름 파악")
                active_df = df[df['당일(%)'].abs() >= 3.0]
                if not active_df.empty:
                    top_mover = active_df.loc[active_df['당일(%)'].abs().idxmax()]
                    st.error(f"🚨 **[급변동 감지]** **{top_mover['티커']}** 종목이 **{get_color_text(top_mover['당일(%)'])}** 급변동 중입니다.")
                    st.code(f"내 포트폴리오의 [{top_mover['티커']}] 종목이 {top_mover['당일(%)']:+.2f}% 급변동 중이다. 실시간 뉴스를 찾아라.", language="markdown")
                else: st.success("✔️ 기준치(±3%)를 초과하는 실시간 급변동 종목이 없습니다.")

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
            with b1: st.metric("[1칸] 누적 배당금(USD)", f"${total_dividend_usd_all:,.2f}", "현금흐름", delta_color="normal")
            with b2: st.metric("[2칸] 누적 실현손익(USD)", f"${box2_profit_usd:,.2f}", "매도차익+배당")
            with b3: st.metric("[3칸] 총 확정수익(KRW)", f"{int(box3_profit_krw):,} 원", "환전 Lock-in 합산")
            with b4: st.metric("[4칸] 미환전 달러잔고", f"${usd_cash_balance:,.2f}", "예수금 일치", delta_color="off")

    with tab2:
        st.subheader("🌍 매크로 경제 지표 종합 상황판")
        components.html('''<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>{"exchanges": [],"dataSource": "SPX500","grouping": "sector","blockSize": "market_cap_basic","blockColor": "change","locale": "kr","colorTheme": "light","hasTopBar": false,"isDataSetEnabled": false,"isZoomEnabled": true,"hasSymbolTooltip": true,"width": "100%","height": "500"}</script></div>''', height=500)
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("🇺🇸 USD/KRW 환율", f"{macro_cache['USDKRW']['live']:,.2f} 원", f"{macro_cache['USDKRW']['change']:.2f} 원")
        m2.metric("미국 10년물 국채", f"{macro_cache['TNX']['live']:.3f} %", f"{macro_cache['TNX']['change']:.3f} %p", delta_color="inverse")
        m3.metric("🛢️ WTI 원유", f"${macro_cache['WTI']['live']:.2f}", f"${macro_cache['WTI']['change']:.2f}")

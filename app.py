# app.py
import streamlit as st
import pandas as pd
import datetime
import pytz

# 우리가 만든 3개의 모듈(부품)에서 필요한 기능만 쏙쏙 뽑아옵니다.
from config import KOR_NAMES, normalize_category
from data_engine import load_data, add_trade, get_macro_data, fetch_market_data, get_all_us_tickers
from ui_components import render_summary, render_portfolio_table, render_analysis_report, render_macro_tab

st.set_page_config(page_title="한결 퀀트 포트폴리오", layout="wide", page_icon="📈")

st.title("📈 한결 퀀트 & 매크로 자산관리 비서")
st.write("V6.0: 100% 모듈화 달성 (초경량 관제탑 아키텍처 적용)")

# ==========================================
# 세션 스테이트 초기화 (중복 클릭 방지용)
# ==========================================
if 'last_trade_hash' not in st.session_state:
    st.session_state['last_trade_hash'] = None

# ==========================================
# 사이드바 (매매/배당 기록 관제)
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
# 메인 대시보드 렌더링 관제
# ==========================================
df_trades = load_data()

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
        return normalize_category(group_map.get(ticker.upper(), '기타 (Others)'))

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
        
        with st.spinner('초경량 모듈형 퀀트 엔진 가동 중...'):
            fetched_data = fetch_market_data(tickers_tuple)
            trading_dates = fetched_data['trading_dates']
            sp500_reg = fetched_data['sp500_reg']
            
            total_value_usd, total_invested_usd, total_daily_change_usd, total_fx_gain_loss_krw = 0.0, 0.0, 0.0, 0.0
            total_dividend_usd_all = sum(v['총배당USD'] for v in portfolio.values())
            
            results, yesterday_recap, error_tickers = [], [], []
            
            ny_tz = pytz.timezone('America/New_York')
            now_kr = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
            now_ny = datetime.datetime.now(ny_tz)
            
            if now_ny.time() >= datetime.time(16, 0):
                valid_dates = [d for d in trading_dates if d <= now_ny.date()]
            else:
                valid_dates = [d for d in trading_dates if d < now_ny.date()]
                
            if len(valid_dates) >= 2:
                target_date, prev_target_date = valid_dates[-1], valid_dates[-2]
            else:
                target_date = now_ny.date()
                prev_target_date = target_date - datetime.timedelta(days=1)
            last_closed_date_str = target_date.strftime('%m/%d')

            t_val = now_ny.hour + now_ny.minute / 60.0
            is_market_closed = False
            
            if now_ny.weekday() >= 5: 
                m_state, price_basis_label, change_label, is_market_closed = "⚫ 주말 (애프터 마켓 최종 마감 가격 유지)", "애프터 마켓 최종 마감가", "직전 애프터 누적", True
            elif 4.0 <= t_val < 9.5:
                m_state, price_basis_label, change_label = "🟡 프리마켓 진행 중", "실시간 프리마켓 가격", "오늘의 변동-프리마켓"
            elif 9.5 <= t_val < 16.0:
                m_state, price_basis_label, change_label = "🟢 본장 진행 중", "실시간 본장 가격", "오늘의 변동-본장"
            elif 16.0 <= t_val < 20.0:
                m_state, price_basis_label, change_label = "🔵 애프터 마켓 진행 중", "실시간 애프터 마켓 가격", "오늘의 변동-애프터 마켓"
            else:
                m_state, price_basis_label, change_label, is_market_closed = "⚪ 데이마켓 진행 중 (시세 표출: 직전 애프터마켓 최종가)", "애프터 마켓 최종 마감가", "직전 애프터 누적", True
                
            market_time_info = f"🕒 **조회 시점:** {now_kr.strftime('%Y년 %m월 %d일 %H:%M')} (KST)\n\n**시장 상태:** {m_state}"

            for ticker, info in portfolio.items():
                shares = float(info['수량'])
                avg_usd_price = float(info['총투자금USD']) / shares if shares > 0 else 0
                avg_purchase_fx = float(info['총투자금KRW']) / float(info['총투자금USD']) if info['총투자금USD'] > 0 else current_live_fx
                category, kor_name = get_category(ticker), KOR_NAMES.get(ticker, ticker)
                
                stock_data = fetched_data['STOCKS'].get(ticker, {'df_1d': pd.DataFrame(), 'df_5m': pd.DataFrame()})
                df_1d, df_5m = stock_data['df_1d'], stock_data['df_5m']
                df_5m_reg = df_5m.between_time('09:30', '16:00') if not df_5m.empty else pd.DataFrame()
                    
                def get_exact_close(d_target):
                    if not df_1d.empty and 'date' in df_1d.columns:
                        match_1d = df_1d[df_1d['date'] == d_target]
                        if not match_1d.empty and pd.notna(match_1d['Close'].iloc[-1]): return float(match_1d['Close'].iloc[-1])
                    if not df_5m_reg.empty:
                        match_5m = df_5m_reg[df_5m_reg.index.date == d_target]
                        if not match_5m.empty and pd.notna(match_5m['Close'].iloc[-1]): return float(match_5m['Close'].iloc[-1])
                    return 0.0

                t_close, d_close = get_exact_close(target_date), get_exact_close(prev_target_date)
                c_price = float(df_5m.dropna(subset=['Close'])['Close'].iloc[-1]) if not df_5m.empty else t_close
                    
                if c_price == 0.0 or t_close == 0.0:
                    if shares > 0: error_tickers.append(ticker)
                    continue

                y_change = ((t_close - d_close) / d_close) * 100 if d_close > 0 else 0.0
                y_value, dby_value = t_close * shares, d_close * shares
                
                if shares > 0 and t_close != d_close:
                    yesterday_recap.append({"종목": kor_name, "그룹": category, "어제변동률": y_change, "어제가치": y_value, "그제가치": dby_value, "변동액": y_value - dby_value})
                
                value_usd = c_price * shares
                change_dollar = (c_price - t_close) * shares if t_close > 0 else 0.0
                return_percent = ((c_price - avg_usd_price) / avg_usd_price) * 100 if avg_usd_price > 0 else 0.0
                daily_percent = ((c_price - t_close) / t_close) * 100 if t_close > 0 else 0.0
                
                div_usd = float(info['총배당USD'])
                stock_fx_gain = info['총투자금USD'] * (current_live_fx - avg_purchase_fx) if shares > 0 and info['총투자금USD'] > 0 else 0.0
                div_fx_gain = (div_usd * current_live_fx) - float(info['총배당KRW']) if div_usd > 0 else 0.0
                total_item_fx_gain = stock_fx_gain + div_fx_gain
                
                total_value_usd += value_usd
                total_daily_change_usd += change_dollar
                total_invested_usd += float(info['총투자금USD'])
                total_fx_gain_loss_krw += total_item_fx_gain
                
                if shares > 0 or div_usd > 0:
                    results.append({"티커": ticker, "종목명": kor_name, "그룹": category, "보유 수량": shares, "평단가 ($)": round(avg_usd_price, 2), "현재가 ($)": round(c_price, 2), "매입환율": round(avg_purchase_fx, 2), "누적배당($)": round(div_usd, 2), "주가수익(%)": round(return_percent, 2), "당일 변동 (%)": round(daily_percent, 2), "환차손익(KRW)": int(total_item_fx_gain), "평가액 ($)": round(value_usd, 2)})

            def get_sp500_close(d_target):
                if not sp500_reg.empty:
                    match_5m = sp500_reg[sp500_reg.index.date == d_target]
                    if not match_5m.empty and pd.notna(match_5m['Close'].iloc[-1]): return float(match_5m['Close'].iloc[-1])
                return 0.0
                
            g_prev = get_sp500_close(prev_target_date)
            sp500_change = ((get_sp500_close(target_date) - g_prev) / g_prev) * 100 if g_prev > 0 else 0.0

            for row in results: row["비중"] = (row["평가액 ($)"] / total_value_usd) * 100 if total_value_usd > 0 else 0.0
            total_profit_usd_only = total_value_usd - total_invested_usd
            total_all_time_usd_tr = ((total_value_usd + total_dividend_usd_all - total_invested_usd) / total_invested_usd) * 100 if total_invested_usd > 0 else 0.0
            total_value_krw = total_value_usd * current_live_fx if current_live_fx > 0 else 0.0
            total_invested_krw = sum(portfolio[tk]['총투자금KRW'] for tk in portfolio)
            total_dividend_current_krw = total_dividend_usd_all * current_live_fx if current_live_fx > 0 else 0.0
            total_profit_krw_tr = (total_value_krw + total_dividend_current_krw) - total_invested_krw if current_live_fx > 0 else 0.0
            total_return_krw_tr = (total_profit_krw_tr / total_invested_krw) * 100 if (total_invested_krw > 0 and current_live_fx > 0) else 0.0

            # UI 모듈을 호출하여 화면에 그림 그리기
            st.info(market_time_info)
            if current_live_fx == 0.0: st.error("🚨 **[환율 데이터 오류]** 실시간 환율 수신 불가.")
            if error_tickers: st.error(f"🚨 **[데이터 수신 오류]** 일시적인 서버 지연 누락: **{', '.join(set(error_tickers))}**")
            
            render_summary(total_value_usd, price_basis_label, total_daily_change_usd, change_label, total_dividend_usd_all, total_all_time_usd_tr, total_profit_usd_only, total_return_krw_tr, total_profit_krw_tr, total_value_krw, total_fx_gain_loss_krw)
            
            if results:
                df = render_portfolio_table(results)
                render_analysis_report(yesterday_recap, sp500_change, last_closed_date_str, df, is_market_closed, m_state, now_kr)

        with tab2:
            render_macro_tab(macro_cache['USDKRW'], macro_cache['TNX'], macro_cache['WTI'])

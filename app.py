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

st.set_page_config(page_title="한결 퀀트 포트폴리오", layout="wide", page_icon="📈")

st.title("📈 한결 퀀트 & 매크로 자산관리 비서")
st.write("V3.3: 전 종목 티커 자동완성 & 자산군 동적 라우팅 적용")

# ==========================================
# 1. 백엔드 데이터베이스 연결 및 제어 로직
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

@st.cache_data(ttl=60)
def load_data():
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("내 주식 장부").sheet1
        return pd.DataFrame(sheet.get_all_records())
    except Exception as e:
        return pd.DataFrame()

def add_trade(date_str, ticker, trade_type, qty, price, group):
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("내 주식 장부").sheet1
        sheet.append_row([str(date_str), str(ticker).upper(), str(trade_type), float(qty), float(price), str(group)])
        return True
    except Exception as e:
        return False

@st.cache_data(ttl=86400)
def get_all_us_tickers():
    try:
        # SEC endpoint block 우회 또는 실패시 사용할 수 있는 광범위한 기본 리스트
        headers = {'User-Agent': 'QuantPortfolioAdmin/1.0 (contact@quantadmin.com)'}
        url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            ticker_list = []
            for item in data.values():
                tk = item['ticker'].replace('-', '.')
                title = item['title']
                ticker_list.append(f"{tk} | {title}")
                
            ticker_list.sort()
            return ["직접 입력 (티커 수동 입력)"] + ticker_list
        else:
            raise Exception("SEC API Error")
    except Exception:
        fallback_tickers = [
            "AAPL | Apple Inc.", "ABBV | AbbVie Inc.", "AMZN | Amazon.com Inc.", 
            "ARQQ | Arqit Quantum Inc.", "AVGO | Broadcom Inc.", "BAC | Bank of America Corp", 
            "BRK.B | Berkshire Hathaway Inc.", "CVX | Chevron Corp.", "DIA | SPDR Dow Jones Industrial Average ETF", 
            "GOOGL | Alphabet Inc.", "HD | Home Depot Inc.", "IBM | International Business Machines Corp.", 
            "IWM | iShares Russell 2000 ETF", "JEPI | JPMorgan Equity Premium Income ETF", "JNJ | Johnson & Johnson", 
            "JPM | JPMorgan Chase & Co.", "KO | Coca-Cola Co.", "LMT | Lockheed Martin Corp.", 
            "MA | Mastercard Inc.", "META | Meta Platforms Inc.", "MRK | Merck & Co. Inc.", 
            "MSFT | Microsoft Corp.", "NEE | NextEra Energy Inc.", "NVDA | NVIDIA Corp.", 
            "PEP | PepsiCo Inc.", "PG | Procter & Gamble Co.", "QQQ | Invesco QQQ Trust", 
            "RGTI | Rigetti Computing Inc.", "SCHD | Schwab US Dividend Equity ETF", "SGOV | iShares 0-3 Month Treasury Bond ETF", 
            "SOXX | iShares Semiconductor ETF", "SPCX | SPAC and New Issue ETF", "SPY | SPDR S&P 500 ETF Trust", 
            "TLT | iShares 20+ Year Treasury Bond ETF", "TQQQ | ProShares UltraPro QQQ", "TSLA | Tesla Inc.", 
            "UNH | UnitedHealth Group Inc.", "V | Visa Inc.", "VOO | Vanguard S&P 500 ETF", "XOM | Exxon Mobil Corp."
        ]
        return ["직접 입력 (티커 수동 입력)"] + fallback_tickers

# ==========================================
# 2. 사이드바: 매매 컨트롤러 (Input Form)
# ==========================================
all_us_tickers = get_all_us_tickers()

with st.sidebar:
    st.header("⚡ 스마트 트레이딩 룸")
    if len(all_us_tickers) > 100:
        st.caption(f"미국 상장 {len(all_us_tickers)-1:,}개 전 종목 데이터 연동됨")
    else:
        st.caption("주요 티커 데이터 연동됨 (수동 입력 가능)")
    
    with st.form(key='trade_form'):
        t_date = st.date_input("체결 날짜", datetime.date.today())
        
        selected_option = st.selectbox("🔍 종목 티커/회사명 검색", all_us_tickers)
        
        if selected_option == "직접 입력 (티커 수동 입력)":
            t_ticker = st.text_input("티커 직접 입력 (예: RGTI)").upper().strip()
        else:
            t_ticker = selected_option.split(" | ")[0].strip()
            
        t_type = st.selectbox("구분", ["매수", "매도"])
        t_qty = st.number_input("체결 수량", min_value=0.00001, format="%.6f", step=0.1)
        t_price = st.number_input("체결 가격 ($)", min_value=0.01, format="%.2f", step=1.0)
        
        group_list = ["코어 (Core)", "방어 (Defensive)", "우량주 (Blue Chip)", "모험주 (Adventure)", "현금/배당 (Cash&DRIP)", "기타 (Others)"]
        t_group = st.selectbox("🧩 자산군 그룹 지정", group_list)
        
        submit_btn = st.form_submit_button(label="장부에 즉시 기록")
        
        if submit_btn:
            if t_ticker:
                with st.spinner("구글 시트 연동 중..."):
                    success = add_trade(t_date, t_ticker, t_type, t_qty, t_price, t_group)
                    if success:
                        st.success(f"[{t_ticker}] 기록 완료! 장부를 동기화합니다.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("기록 실패. 구글 시트 F열에 '그룹' 칸을 만들었는지 확인해라.")
            else:
                st.warning("티커를 선택하거나 입력해라.")

# ==========================================
# 3. 프론트엔드 대시보드 렌더링
# ==========================================
df_trades = load_data()

if df_trades.empty:
    st.warning("데이터를 불러오는 중이거나 구글 장부가 비어있습니다.")
else:
    group_map = {
        'VOO': '코어 (Core)', 'SGOV': '코어 (Core)',
        'KO': '방어 (Defensive)', 'BAC': '방어 (Defensive)', 'NEE': '방어 (Defensive)', 'LMT': '방어 (Defensive)',
        'IBM': '우량주 (Blue Chip)', 'SPCX': '우량주 (Blue Chip)', 'GOOGL': '우량주 (Blue Chip)',
        'RGTI': '모험주 (Adventure)', 'ARQQ': '모험주 (Adventure)'
    }
    
    if '그룹' in df_trades.columns:
        for _, row in df_trades.iterrows():
            tk = str(row.get('종목', '')).strip().upper()
            grp = str(row.get('그룹', '')).strip()
            if tk and grp:
                group_map[tk] = grp
                
    def get_category(ticker):
        return group_map.get(ticker.upper(), '기타 (Others)')

    tab1, tab2 = st.tabs(["💰 내 자산 대시보드", "🌍 매크로 종합 상황판"])
    
    with tab1:
        portfolio = {}
        for _, row in df_trades.iterrows():
            ticker = str(row.get('종목', '')).strip().upper()
            trade_type = str(row.get('구분', '')).strip()
            try:
                qty, price = float(row.get('수량', 0)), float(row.get('가격($)', 0))
            except: continue
                
            if ticker not in portfolio: portfolio[ticker] = {'수량': 0.0, '총투자금': 0.0}
                
            if trade_type == '매수':
                portfolio[ticker]['수량'] += qty
                portfolio[ticker]['총투자금'] += (qty * price)
            elif trade_type == '매도' and portfolio[ticker]['수량'] > 0:
                avg_price = portfolio[ticker]['총투자금'] / portfolio[ticker]['수량']
                portfolio[ticker]['수량'] -= qty
                portfolio[ticker]['총투자금'] -= (qty * avg_price)

        portfolio = {k: v for k, v in portfolio.items() if v['수량'] > 0}
        tickers = list(portfolio.keys())
        
        with st.spinner('하이브리드 엔진으로 정밀 데이터를 조립 중입니다... (공식 일봉 우선 검색 적용)'):
            total_value, total_invested, total_daily_change = 0.0, 0.0, 0.0
            results = []
            yesterday_recap = [] 
            sp500_change = 0.0
            
            ny_tz = pytz.timezone('America/New_York')
            now_kr = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
            now_ny = datetime.datetime.now(ny_tz)
            
            sp500_5m = yf.Ticker("^GSPC").history(period="15d", interval="5m")
            if not sp500_5m.empty:
                if sp500_5m.index.tz is None:
                    sp500_5m.index = sp500_5m.index.tz_localize('UTC').tz_convert(ny_tz)
                else:
                    sp500_5m.index = sp500_5m.index.tz_convert(ny_tz)
                    
                sp500_reg = sp500_5m.between_time('09:30', '16:00')
                trading_dates = sorted(list(set(sp500_reg.index.date)))
                
                if now_ny.time() >= datetime.time(16, 0):
                    valid_dates = [d for d in trading_dates if d <= now_ny.date()]
                else:
                    valid_dates = [d for d in trading_dates if d < now_ny.date()]
                    
                if len(valid_dates) >= 2:
                    target_date = valid_dates[-1]
                    prev_target_date = valid_dates[-2]
                    last_closed_date_str = target_date.strftime('%m/%d')
                else:
                    st.error("시장 거래일 기준 달력을 생성할 수 없습니다.")
                    st.stop()
            else:
                st.error("벤치마크 데이터를 가져올 수 없습니다.")
                st.stop()
            
            current_kr_time_str = now_kr.strftime('%Y년 %m월 %d일 %H:%M')
            t_val = now_ny.hour + now_ny.minute / 60.0
            is_market_closed = False
            
            if now_ny.weekday() >= 5: 
                m_state = "⚫ 주말 (애프터 마켓 최종 마감 가격 유지)"
                price_basis_label = "애프터 마켓 최종 마감 가격"
                is_market_closed = True
            elif 4.0 <= t_val < 9.5:
                m_state = "🟡 프리마켓 진행 중"
                price_basis_label = "실시간 프리마켓 가격"
            elif 9.5 <= t_val < 16.0:
                m_state = "🟢 본장 진행 중"
                price_basis_label = "실시간 본장 가격"
            elif 16.0 <= t_val < 20.0:
                m_state = "🔵 애프터 마켓 진행 중"
                price_basis_label = "실시간 애프터 마켓 가격"
            else:
                m_state = "⚫ 애프터 마감 (프리마켓 개장 전)"
                price_basis_label = "애프터 마켓 최종 마감 가격"
                is_market_closed = True
                
            market_time_info = f"🕒 **조회 시점:** {current_kr_time_str} (한국시간 기준)\n\n**현재 시장 상태:** {m_state}"

            for ticker, info in portfolio.items():
                shares = float(info['수량'])
                avg_price = float(info['총투자금']) / shares if shares > 0 else 0
                category = get_category(ticker)
                
                ticker_obj = yf.Ticker(ticker)
                
                df_1d = ticker_obj.history(period="15d", interval="1d")
                df_5m = ticker_obj.history(period="15d", interval="5m", prepost=True)
                
                if not df_1d.empty:
                    if df_1d.index.tz is None:
                        df_1d.index = df_1d.index.tz_localize(ny_tz)
                    else:
                        df_1d.index = df_1d.index.tz_convert(ny_tz)
                    df_1d['date'] = df_1d.index.date
                    
                if not df_5m.empty:
                    if df_5m.index.tz is None:
                        df_5m.index = df_5m.index.tz_localize('UTC').tz_convert(ny_tz)
                    else:
                        df_5m.index = df_5m.index.tz_convert(ny_tz)
                    df_5m_reg = df_5m.between_time('09:30', '16:00')
                    
                def get_exact_close(d_target):
                    if not df_1d.empty:
                        match_1d = df_1d[df_1d['date'] == d_target]
                        if not match_1d.empty and pd.notna(match_1d['Close'].iloc[-1]):
                            return float(match_1d['Close'].iloc[-1])
                    if not df_5m.empty:
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
                
                if t_close == 0.0:
                    continue
                
                y_change = ((t_close - d_close) / d_close) * 100 if d_close > 0 else 0.0
                y_value = t_close * shares
                dby_value = d_close * shares
                
                yesterday_recap.append({
                    "종목": ticker, 
                    "그룹": category,
                    "어제변동률": y_change,
                    "어제가치": y_value,
                    "그제가치": dby_value,
                    "변동액": y_value - dby_value
                })
                
                value = c_price * shares
                change_dollar = (c_price - t_close) * shares
                return_percent = ((c_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0.0
                daily_percent = ((c_price - t_close) / t_close) * 100 if t_close > 0 else 0.0
                
                total_value += value
                total_daily_change += change_dollar
                total_invested += float(info['총투자금'])
                
                results.append({
                    "종목": ticker,
                    "그룹": category,
                    "보유 수량": shares,
                    "평단가 ($)": round(avg_price, 2),
                    "현재가 ($)": round(c_price, 2),
                    "수익률 (%)": round(return_percent, 2),
                    "평가액 ($)": round(value, 2),
                    "당일 변동 (%)": round(daily_percent, 2)
                })
            
            sp_1d = yf.Ticker("^GSPC").history(period="15d", interval="1d")
            if not sp_1d.empty:
                if sp_1d.index.tz is None: sp_1d.index = sp_1d.index.tz_localize(ny_tz)
                else: sp_1d.index = sp_1d.index.tz_convert(ny_tz)
                sp_1d['date'] = sp_1d.index.date
                
            def get_sp500_close(d_target):
                if not sp_1d.empty:
                    match_1d = sp_1d[sp_1d['date'] == d_target]
                    if not match_1d.empty and pd.notna(match_1d['Close'].iloc[-1]) and float(match_1d['Close'].iloc[-1]) > 0:
                        return float(match_1d['Close'].iloc[-1])
                match_5m = sp500_reg[sp500_reg.index.date == d_target]
                if not match_5m.empty and pd.notna(match_5m['Close'].iloc[-1]) and float(match_5m['Close'].iloc[-1]) > 0:
                    return float(match_5m['Close'].iloc[-1])
                return 0.0
                
            g_target = get_sp500_close(target_date)
            g_prev = get_sp500_close(prev_target_date)
            
            if g_target > 0 and g_prev > 0:
                sp500_change = ((g_target - g_prev) / g_prev) * 100

            for row in results:
                row["비중"] = (row["평가액 ($)"] / total_value) * 100 if total_value > 0 else 0.0

            total_all_time_return = ((total_value - total_invested) / total_invested) * 100 if total_invested > 0 else 0.0

            st.info(market_time_info)
            col1, col2 = st.columns(2)
            
            col1.metric(
                label=f"총 자산 평가액 (USD) - [{price_basis_label}]", 
                value=f"${total_value:,.2f}", 
                delta=f"{total_daily_change:,.2f} USD (오늘의 변동)"
            )
            col2.metric(
                label="총 누적 수익률", 
                value=f"{total_all_time_return:+.2f}%", 
                delta=f"{(total_value - total_invested):,.2f} USD (누적 총 손익)"
            )
            
            st.divider()
            
            if results:
                df = pd.DataFrame(results)
                df = df.sort_values(by="비중", ascending=False).reset_index(drop=True)
                
                st.subheader("📊 포트폴리오 상세 및 리스크 배분 현황")
                
                fig = px.pie(df, values='평가액 ($)', names='그룹', hole=0.4, 
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "종목": st.column_config.TextColumn("종목명"),
                        "그룹": st.column_config.TextColumn("자산군 그룹"),
                        "보유 수량": st.column_config.NumberColumn("수량 (주)", format="%.4f"),
                        "평단가 ($)": st.column_config.NumberColumn("평단가 ($)", format="$%.2f"),
                        "현재가 ($)": st.column_config.NumberColumn("현재가 ($)", format="$%.2f"),
                        "수익률 (%)": st.column_config.NumberColumn("수익률 (%)", format="%.2f%%"),
                        "당일 변동 (%)": st.column_config.NumberColumn("당일 변동 (%)", format="%.2f%%"),
                        "평가액 ($)": st.column_config.NumberColumn("평가액 ($)", format="$%.2f"),
                        "비중": st.column_config.ProgressColumn(
                            "비중 (%)",
                            help="총 자산 대비 비중",
                            format="%.2f%%",
                            min_value=0,
                            max_value=100
                        )
                    }
                )
                
                st.divider()
                
                st.header("📰 시황 분석 리포트 (투트랙)")
                
                st.subheader(f"🌙 1. 전일장 마감 요약 (미국시간 {last_closed_date_str} 정규장 마감 기준)")
                if yesterday_recap:
                    df_y = pd.DataFrame(yesterday_recap)
                    
                    total_dby = df_y['그제가치'].sum()
                    total_y = df_y['어제가치'].sum()
                    total_change_dollar = total_y - total_dby
                    total_change_pct = (total_change_dollar / total_dby * 100) if total_dby > 0 else 0.0
                    
                    outperform = total_change_pct - sp500_change
                    win_lose = "상회" if outperform > 0 else "하회"
                    
                    st.markdown(f"**📌 계좌 총괄 성적:** 전일 대비 **{get_color_text(total_change_pct)}** ({get_color_text(total_change_dollar, is_percent=False)})")
                    st.write(f"👉 시장(S&P 500: {get_color_text(sp500_change)}) 흐름 대비 내 자산 배분이 **{abs(outperform):.2f}%p {win_lose}**했습니다.")
                    
                    st.write("---")
                    
                    st.markdown("**🧩 섹터/그룹별 기여도**")
                    grp_agg = df_y.groupby('그룹').agg({'그제가치': 'sum', '어제가치': 'sum', '변동액': 'sum'}).reset_index()
                    grp_agg['수익률'] = (grp_agg['변동액'] / grp_agg['그제가치']) * 100
                    grp_agg = grp_agg.sort_values(by='수익률', ascending=False)
                    
                    grp_texts = []
                    for _, row in grp_agg.iterrows():
                        grp_texts.append(f"**{row['그룹']}** {get_color_text(row['수익률'])}")
                    st.write(" | ".join(grp_texts))
                    
                    st.write("---")
                    
                    st.markdown("**🏆 포트폴리오 양극단 특징주**")
                    valid_df_y = df_y.dropna(subset=['어제변동률'])
                    if not valid_df_y.empty:
                        top_gainer = valid_df_y.loc[valid_df_y['어제변동률'].idxmax()]
                        top_loser = valid_df_y.loc[valid_df_y['어제변동률'].idxmin()]
                        
                        c_gainer, c_loser = st.columns(2)
                        with c_gainer:
                            st.success(f"🚀 **최고 효자:** {top_gainer['종목']} ({get_color_text(top_gainer['어제변동률'])})")
                        with c_loser:
                            st.error(f"📉 **최대 구멍:** {top_loser['종목']} ({get_color_text(top_loser['어제변동률'])})")
                    else:
                        st.info("비교할 수 있는 유효한 등락 데이터가 없습니다.")
                else:
                    st.info("💡 전일 장마감 데이터가 존재하지 않거나 현재 수집 불가능한 상태입니다.")

                st.write("") 

                st.subheader("⚡ 2. 실시간 흐름 파악 (당일 라이브)")
                
                if is_market_closed:
                    st.info("💡 **현재 프리마켓 개장 전(또는 주말 장 마감)이므로 실시간 흐름 파악 데이터가 없습니다.**\n\n(미국 증시 개장 시간에 다시 확인해 주세요.)")
                elif len(df) > 0:
                    top_mover = df.loc[df['당일 변동 (%)'].abs().idxmax()]
                    top_ticker = top_mover['종목']
                    top_change = top_mover['당일 변동 (%)']
                    
                    if abs(top_change) >= 3.0:
                        live_color_text = get_color_text(top_change)
                        st.error(f"🚨 **[특징주 감지: {current_m_state}]**\n\n**조회 시점:** {current_kr_time_str} (한국시간 기준)\n\n현재 장에서 **{top_ticker}** 종목이 **{live_color_text}** 급변동 중입니다.")
                        st.write("해당 움직임의 원인과 대응 전략을 파악하기 위해 아래 텍스트를 복사하여 AI 비서(채팅창)에게 질문하세요.")
                        
                        ai_prompt = f"[{current_kr_time_str} (한국시간) / {current_m_state} 기준]\n지금 내 포트폴리오의 [{top_ticker}] 종목이 실시간으로 {top_change:+.2f}% 급변동하고 있다. \n반드시 1단계: 실시간 가격 확인, 2단계: 뉴스 매칭, 3단계: 정합성 검증의 프로세스를 거쳐서 이 변동의 진짜 이유를 외신과 공시 데이터를 기반으로 찾아내라. \n감언이설이나 뻔한 소리는 빼고, 현재 상황이 내 포트폴리오에 미칠 영향과 내 논리적 가정에 구멍이 있다면 직설적으로 비판하면서 명확한 액션 플랜을 제시해."
                        
                        st.code(ai_prompt, language="markdown")
                        st.markdown(f"👉 **[🚀 실시간 뉴스 직접 체크하기 (SAVE 앱 연결)](https://saveticker.com)**")
                    else:
                        st.success("✔️ **[현재 라이브 기준]** 기준치(±3%)를 초과하는 실시간 특징 동향 종목이 없습니다. 보여줄 데이터가 없으므로 브리핑을 생략합니다.")
                else:
                    st.info("💡 당일 실시간 거래 데이터를 분석할 수 없습니다.")

    with tab2:
        st.subheader("🌍 매크로 경제 지표 종합 대시보드")
        st.markdown("### 1. S&P 500 섹터 히트맵 (TradingView)")
        components.html(
            '''
            <div class="tradingview-widget-container">
              <div class="tradingview-widget-container__widget"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>
              {
              "exchanges": [],
              "dataSource": "SPX500",
              "grouping": "sector",
              "blockSize": "market_cap_basic",
              "blockColor": "change",
              "locale": "kr",
              "colorTheme": "light",
              "hasTopBar": false,
              "isDataSetEnabled": false,
              "isZoomEnabled": true,
              "hasSymbolTooltip": true,
              "width": "100%",
              "height": "500"
            }
              </script>
            </div>
            ''', height=500
        )
        
        st.divider()
        st.markdown("### 2. Fear and Greed Index (공포와 탐욕 지수)")
        st.markdown("👉 **[🔗 CNN Fear & Greed Index 실시간 확인하기 (클릭)](https://edition.cnn.com/markets/fear-and-greed)**")
        
        st.divider()
        st.markdown("### 3. CME FedWatch Tool (금리 예측)")
        st.markdown("👉 **[🔗 CME FedWatch Tool 실시간 확인하기 (클릭)](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)**")

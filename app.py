import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
import json
import plotly.express as px
import streamlit.components.v1 as components
import datetime
import pytz

st.set_page_config(page_title="한결 퀀트 포트폴리오", layout="wide", page_icon="📈")

st.title("📈 한결 퀀트 & 매크로 자산관리 비서")
st.write("구글 시트 기반 자동화 포트폴리오 및 3단계 시황 브리핑 시스템")

# [Helper] 컬러 텍스트 포맷터 (텍스트 전용)
def get_color_text(val, is_percent=True):
    sign = "+" if val > 0 else ""
    fmt = f"{val:.2f}"
    if is_percent: res = f"{sign}{fmt}%"
    else: res = f"{sign}${abs(val):.2f}"
    
    if val > 0: return f":green[{res}]"
    elif val < 0: return f":red[{res}]"
    else: return f":gray[{res}]"

# 1. 구글 시트 연동
@st.cache_data(ttl=60)
def load_data():
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("내 주식 장부").sheet1
        return pd.DataFrame(sheet.get_all_records())
    except Exception as e:
        return pd.DataFrame()

# 2. 종목별 자산군 분류
def get_category(ticker):
    ticker = ticker.upper()
    if ticker in ['VOO', 'SGOV']: return '코어 (Core)'
    elif ticker in ['KO', 'BAC', 'NEE', 'LMT']: return '방어 (Defensive)'
    elif ticker in ['IBM', 'SPCX', 'GOOGL']: return '우량주 (Blue Chip)'
    elif ticker in ['RGTI', 'ARQQ']: return '모험주 (Adventure)'
    else: return '기타 (Others)'

df_trades = load_data()

if df_trades.empty:
    st.warning("데이터를 불러오는 중이거나 구글 장부가 비어있습니다.")
else:
    tab1, tab2 = st.tabs(["💰 내 자산 대시보드", "🌍 매크로 종합 상황판"])
    
    with tab1:
        portfolio = {}
        for _, row in df_trades.iterrows():
            ticker = str(row['종목']).strip().upper()
            trade_type = str(row['구분']).strip()
            try:
                qty, price = float(row['수량']), float(row['가격($)'])
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
        
        with st.spinner('실시간 시세와 차트를 렌더링 중입니다...'):
            total_value, total_invested, total_daily_change = 0.0, 0.0, 0.0
            results = []
            yesterday_recap = [] 
            
            market_time_info = "가격 정보를 불러오는 중입니다..."
            time_captured = False
            current_kr_time_str = ""
            current_m_state = ""
            
            # 기준일자 계산용 뉴욕 시간 세팅
            ny_tz = pytz.timezone('America/New_York')
            now_ny = datetime.datetime.now(ny_tz)
            today_str = now_ny.strftime('%Y-%m-%d')
            
            for ticker, info in portfolio.items():
                shares = info['수량']
                avg_price = info['총투자금'] / shares
                category = get_category(ticker)
                
                try:
                    live_data = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=True)
                    daily_data = yf.Ticker(ticker).history(period="7d")
                    
                    if len(live_data) > 0 and len(daily_data) >= 2:
                        current_price = live_data['Close'].iloc[-1]
                        
                        # [트랙 1] 어제 데이터 확정 추출 (오늘 날짜 데이터는 완벽히 배제)
                        daily_data.index = daily_data.index.tz_convert(ny_tz)
                        historical_daily = daily_data[daily_data.index.strftime('%Y-%m-%d') < today_str]
                        
                        if len(historical_daily) >= 2:
                            prev_close = historical_daily['Close'].iloc[-1] # 어제 종가
                            dby_close = historical_daily['Close'].iloc[-2]  # 그저께 종가
                            y_change = ((prev_close - dby_close) / dby_close) * 100
                            yesterday_recap.append({"종목": ticker, "어제변동률": y_change})
                        elif len(historical_daily) == 1:
                            prev_close = historical_daily['Close'].iloc[-1]
                        else:
                            prev_close = current_price
                            
                        # [트랙 2] 라이브 시간 및 상태 추출
                        if not time_captured:
                            last_time = live_data.index[-1]
                            if last_time.tzinfo is None:
                                ny_time = last_time.tz_localize('UTC').tz_convert('America/New_York')
                            else:
                                ny_time = last_time.tz_convert('America/New_York')
                            
                            kr_time = ny_time.tz_convert('Asia/Seoul')
                            current_kr_time_str = kr_time.strftime('%Y년 %m월 %d일 %H:%M')
                                
                            t_val = ny_time.hour + ny_time.minute / 60.0
                            if 4.0 <= t_val < 9.5:
                                m_state = "🟡 프리마켓 (Pre-market)"
                            elif 9.5 <= t_val < 16.0:
                                m_state = "🟢 본장 (Regular Market)"
                            elif 16.0 <= t_val < 20.0:
                                m_state = "🔵 애프터마켓 (After-hours)"
                            else:
                                m_state = "⚫ 장 마감 (Closed)"
                                
                            current_m_state = m_state
                            market_time_info = f"🕒 **데이터 기준 시점:** {current_kr_time_str} (한국 시간) | **현재 상태:** {m_state}"
                            time_captured = True
                        
                        value = current_price * shares
                        change_dollar = (current_price - prev_close) * shares
                        return_percent = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
                        daily_percent = ((current_price - prev_close) / prev_close) * 100
                        
                        total_value += value
                        total_invested += info['총투자금']
                        total_daily_change += change_dollar
                        
                        results.append({
                            "종목": ticker,
                            "그룹": category,
                            "보유 수량": shares,
                            "평단가 ($)": round(avg_price, 2),
                            "현재가 ($)": round(current_price, 2),
                            "수익률 (%)": round(return_percent, 2),
                            "평가액 ($)": round(value, 2),
                            "당일 변동 (%)": round(daily_percent, 2)
                        })
                except: pass
            
            # --- 상단: 핵심 지표 ---
            st.info(market_time_info)
            total_all_time_return = ((total_value - total_invested) / total_invested) * 100 if total_invested > 0 else 0
            
            col1, col2 = st.columns(2)
            # st.metric은 기본적으로 양수(초록), 음수(빨강), 0(회색)을 자동으로 지원함.
            col1.metric("총 자산 평가액 (USD)", f"${total_value:,.2f}", f"오늘의 변동: {total_daily_change:+,.2f} USD")
            col2.metric("총 누적 수익률", f"{total_all_time_return:+.2f}%", f"누적 총 손익: {(total_value - total_invested):+,.2f} USD")
            
            st.divider()
            
            # --- 중단: 포트폴리오 상세 및 차트 ---
            if results:
                df = pd.DataFrame(results)
                
                st.subheader("📊 포트폴리오 상세 및 리스크 배분 현황")
                
                fig = px.pie(df, values='평가액 ($)', names='그룹', hole=0.4, 
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # 표 색상 조건부 서식 적용
                def color_positive_negative(val):
                    if isinstance(val, (int, float)):
                        if val > 0: return 'color: #09ab3b' # 초록
                        elif val < 0: return 'color: #ff4b4b' # 빨강
                        else: return 'color: #808495' # 회색
                    return ''
                
                styled_df = df.style.map(color_positive_negative, subset=['수익률 (%)', '당일 변동 (%)'])
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
                
                st.divider()
                
                # --- 하단: 투트랙 시황 브리핑 시스템 ---
                st.header("📰 시황 분석 리포트 (투트랙)")
                
                # [트랙 1] 전일장 마감 결산
                st.subheader("🌙 1. 전일장 마감 정리")
                if yesterday_recap:
                    df_yesterday = pd.DataFrame(yesterday_recap)
                    top_yesterday = df_yesterday.loc[df_yesterday['어제변동률'].abs().idxmax()]
                    y_ticker = top_yesterday['종목']
                    y_change = top_yesterday['어제변동률']
                    
                    y_color_text = get_color_text(y_change)
                    st.write(f"어제 미국 정규장 마감 기준으로 내 포트폴리오에서 가장 큰 변동을 보였던 종목은 **{y_ticker} ({y_color_text})** 였습니다. 이 데이터를 기준으로 오늘의 라이브 장이 측정됩니다.")
                else:
                    st.info("💡 전일 장마감 데이터가 존재하지 않거나 현재 수집 불가능한 상태입니다.")

                st.write("") 

                # [트랙 2] 당일 라이브 스캐너
                st.subheader("⚡ 2. 실시간 흐름 파악 (당일 라이브)")
                if len(df) > 0:
                    top_mover = df.loc[df['당일 변동 (%)'].abs().idxmax()]
                    top_ticker = top_mover['종목']
                    top_change = top_mover['당일 변동 (%)']
                    
                    if abs(top_change) >= 3.0:
                        live_color_text = get_color_text(top_change)
                        st.error(f"🚨 **[특징주 감지: {current_m_state}]**\n\n**조회 시점:** {current_kr_time_str}\n\n현재 장에서 **{top_ticker}** 종목이 **{live_color_text}** 급변동 중입니다.")
                        st.write("해당 움직임의 원인과 대응 전략을 파악하기 위해 아래 텍스트를 복사하여 AI 비서(채팅창)에게 질문하세요.")
                        
                        ai_prompt = f"[{current_kr_time_str} / {current_m_state} 기준]\n지금 내 포트폴리오의 [{top_ticker}] 종목이 실시간으로 {top_change:+.2f}% 급변동하고 있다. \n반드시 1단계: 실시간 가격 확인, 2단계: 뉴스 매칭, 3단계: 정합성 검증의 프로세스를 거쳐서 이 변동의 진짜 이유를 외신과 공시 데이터를 기반으로 찾아내라. \n감언이설이나 뻔한 소리는 빼고, 현재 상황이 내 포트폴리오에 미칠 영향과 내 논리적 가정에 구멍이 있다면 직설적으로 비판하면서 명확한 액션 플랜을 제시해."
                        
                        st.code(ai_prompt, language="markdown")
                        st.markdown(f"👉 **[🚀 실시간 뉴스 직접 체크하기 (SAVE 앱 연결)](https://saveticker.com)**")
                    else:
                        st.success("✔️ **[현재 라이브 기준]** 기준치(±3%)를 초과하는 실시간 특징 동향 종목이 없습니다. 보여줄 데이터가 없으므로 브리핑을 생략합니다.")
                else:
                    st.info("💡 당일 실시간 거래 데이터를 분석할 수 없습니다.")

    with tab2:
        st.subheader("🌍 매크로 경제 지표 종합 대시보드")
        
        st.markdown("### 1. S&P 500 섹터 히트맵 (TradingView)")
        st.write("미국 증시 전반의 붉고 푸른 흐름을 직관적으로 확인하세요.")
        
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
        st.write("시장 참여자들의 실시간 심리 상태를 확인하세요.")
        st.markdown("👉 **[🔗 CNN Fear & Greed Index 실시간 확인하기 (클릭)](https://edition.cnn.com/markets/fear-and-greed)**")
        
        st.divider()
        st.markdown("### 3. CME FedWatch Tool (금리 예측)")
        st.write("미 연준(Fed)의 다음 기준금리 결정 확률을 실시간으로 추적합니다.")
        st.markdown("👉 **[🔗 CME FedWatch Tool 실시간 확인하기 (클릭)](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)**")

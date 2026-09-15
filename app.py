import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
import json
import plotly.express as px
import streamlit.components.v1 as components

st.set_page_config(page_title="한결 퀀트 포트폴리오", layout="wide", page_icon="📈")

st.title("📈 한결 퀀트 & 매크로 자산관리 비서")
st.write("구글 시트 기반 자동화 포트폴리오 및 3단계 시황 브리핑 시스템")

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
    tab1, tab2 = st.tabs(["💰 내 자산 대시보드 (3단계 브리핑)", "🌍 매크로 종합 상황판"])
    
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
            market_time_info = "가격 정보를 불러오는 중입니다..."
            time_captured = False
            
            for ticker, info in portfolio.items():
                shares = info['수량']
                avg_price = info['총투자금'] / shares
                category = get_category(ticker)
                
                try:
                    live_data = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=True)
                    daily_data = yf.Ticker(ticker).history(period="5d")
                    
                    if len(live_data) > 0 and len(daily_data) >= 2:
                        current_price = live_data['Close'].iloc[-1]
                        prev_close = daily_data['Close'].iloc[-2]
                        
                        if not time_captured:
                            last_time = live_data.index[-1]
                            if last_time.tzinfo is None:
                                ny_time = last_time.tz_localize('UTC').tz_convert('America/New_York')
                            else:
                                ny_time = last_time.tz_convert('America/New_York')
                            kr_time = ny_time.tz_convert('Asia/Seoul')
                                
                            t_val = ny_time.hour + ny_time.minute / 60.0
                            if 4.0 <= t_val < 9.5:
                                m_state = "🟡 프리마켓 (Pre-market)"
                            elif 9.5 <= t_val < 16.0:
                                m_state = "🟢 본장 (Regular Market)"
                            elif 16.0 <= t_val < 20.0:
                                m_state = "🔵 애프터마켓 (After-hours)"
                            else:
                                m_state = "⚫ 장 마감 (Closed)"
                                
                            market_time_info = f"🕒 **데이터 기준 시점:** {kr_time.strftime('%Y년 %m월 %d일 %H:%M')} (한국 시간) | **현재 상태:** {m_state}"
                            time_captured = True
                        
                        value = current_price * shares
                        change_dollar = (current_price - prev_close) * shares
                        return_percent = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
                        
                        total_value += value
                        total_invested += info['총투자금']
                        total_daily_change += change_dollar
                        
                        results.append({
                            "종목": ticker,
                            "그룹": category,
                            "보유 수량": shares,
                            "평단가": avg_price,
                            "현재가": current_price,
                            "수익률 (%)": return_percent,
                            "평가액 ($)": value,
                            "일일 변동율": ((current_price - prev_close) / prev_close) * 100
                        })
                except: pass
            
            st.info(market_time_info)
            
            total_all_time_return = ((total_value - total_invested) / total_invested) * 100 if total_invested > 0 else 0
            col1, col2 = st.columns(2)
            col1.metric("총 자산 평가액 (USD)", f"${total_value:,.2f}", f"오늘의 변동: {total_daily_change:,.2f} USD")
            col2.metric("총 누적 수익률", f"{total_all_time_return:.2f}%", f"누적 총 손익: ${(total_value - total_invested):,.2f}")
            
            st.divider()
            
            if results:
                df = pd.DataFrame(results)
                
                st.subheader("📊 포트폴리오 자산군 리스크 배분 현황")
                fig = px.pie(df, values='평가액 ($)', names='그룹', hole=0.4, 
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(df.drop(columns=['일일 변동율']), use_container_width=True, hide_index=True)
                
                st.divider()
                
                st.subheader("🤖 일일 3단계 시황 브리핑 리포트")
                
                if len(df) > 0:
                    top_mover = df.loc[df['일일 변동율'].abs().idxmax()]
                    top_ticker = top_mover['종목']
                    top_change = top_mover['일일 변동율']
                    
                    st.markdown("#### 1단계: 실시간 가격 확인")
                    st.info(f"오늘 포트폴리오 내 최대 변동 종목은 **{top_ticker}** 입니다. (전일 대비 **{top_change:+.2f}%** 변동)")
                    
                    st.markdown("#### 2단계: 핵심 뉴스 매칭 (SAVE 연동)")
                    st.write(f"복잡한 영어 뉴스 대신, 'SAVE'에서 {top_ticker}의 속보와 요약 리포트를 직관적으로 확인하세요!")
                    st.markdown(f"👉 **[🚀 SAVE에서 {top_ticker} 실시간 뉴스 바로보기 (클릭)](https://saveticker.com)**")
                    st.caption("※ 모바일 환경에서는 링크 클릭 시 SAVE 플랫폼으로 즉시 연결됩니다.")
                        
                    st.markdown("#### 3단계: 정합성 검증 (Verification)")
                    if top_change > 3.0:
                        st.success(f"✔️ **검증:** {top_ticker}의 +3% 이상 급등은 강한 매수세 또는 호재 뉴스와 일치할 확률이 높습니다. 단기 과열 여부만 체크하세요.")
                    elif top_change < -3.0:
                        st.error(f"⚠️ **검증:** {top_ticker}의 -3% 이상 급락 발생! 2단계 뉴스에서 악재(실적 미달, 매크로 충격 등)를 반드시 교차 검증해야 합니다.")
                    else:
                        st.warning(f"✔️ **검증:** {top_ticker}의 현재 변동은 특이사항 없는 일반적인 시장 노이즈(보합세) 범위 내에 있습니다.")

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

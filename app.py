import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
import json

st.set_page_config(page_title="한결 포트폴리오", layout="wide")

st.title("📊 자산관리 대시보드")
st.write("구글 시트의 매매 기록을 바탕으로 내 자산을 실시간 계산합니다.")

# 1. 구글 시트 연동 (1분마다 최신화되도록 설정)
@st.cache_data(ttl=60)
def load_data():
    try:
        # 금고(secrets)에서 암호를 꺼내서 구글에 로그인
        creds_dict = json.loads(st.secrets["google_credentials"])
        gc = gspread.service_account_from_dict(creds_dict)
        
        # '내 주식 장부' 파일 열기
        doc = gc.open("내 주식 장부")
        sheet = doc.sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"구글 시트 연결 오류가 발생했습니다: {e}")
        return pd.DataFrame()

df_trades = load_data()

if df_trades.empty:
    st.warning("구글 시트에서 데이터를 불러오지 못했거나 장부가 비어있습니다. '내 주식 장부' 시트를 확인해 주세요.")
else:
    # 2. 매매 기록을 바탕으로 보유 수량 및 평단가 자동 계산!
    portfolio = {}
    for index, row in df_trades.iterrows():
        ticker = str(row['종목']).strip().upper()
        trade_type = str(row['구분']).strip()
        
        try:
            qty = float(row['수량'])
            price = float(row['가격($)'])
        except:
            continue # 숫자가 아닌 빈칸 등이 있으면 안전하게 건너뜀
            
        if ticker not in portfolio:
            portfolio[ticker] = {'수량': 0.0, '총투자금': 0.0}
            
        if trade_type == '매수':
            portfolio[ticker]['수량'] += qty
            portfolio[ticker]['총투자금'] += (qty * price)
        elif trade_type == '매도':
            if portfolio[ticker]['수량'] > 0:
                avg_price = portfolio[ticker]['총투자금'] / portfolio[ticker]['수량']
                portfolio[ticker]['수량'] -= qty
                portfolio[ticker]['총투자금'] -= (qty * avg_price)

    # 수량이 0보다 큰(보유 중인) 종목만 화면에 남기기
    portfolio = {k: v for k, v in portfolio.items() if v['수량'] > 0}

    # 3. 실시간 주가 반영 및 화면 출력
    st.subheader("💰 실시간 내 자산 현황")
    
    with st.spinner('실시간 자산 가치를 계산하는 중입니다...'):
        total_value = 0.0
        total_invested = 0.0
        total_daily_change = 0.0
        results = []
        
        for ticker, info in portfolio.items():
            shares = info['수량']
            if shares <= 0:
                continue
            avg_price = info['총투자금'] / shares
            
            try:
                stock_data = yf.Ticker(ticker).history(period="5d", prepost=True)
                if len(stock_data) >= 2:
                    current_price = stock_data['Close'].iloc[-1]
                    prev_close = stock_data['Close'].iloc[-2]
                    
                    value = current_price * shares
                    change_dollar = (current_price - prev_close) * shares
                    
                    total_value += value
                    total_invested += info['총투자금']
                    total_daily_change += change_dollar
                    
                    # 새로운 항목: 내 평단가 대비 수익률 계산
                    return_percent = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
                    
                    results.append({
                        "종목": ticker,
                        "보유 수량": shares,
                        "평단가": avg_price,
                        "현재가": current_price,
                        "수익률": return_percent,
                        "평가액": value
                    })
            except Exception:
                pass
        
        for row in results:
            row["비중"] = (row["평가액"] / total_value) * 100 if total_value > 0 else 0
            
        base_value = total_value - total_daily_change
        total_change_percent = (total_daily_change / base_value) * 100 if base_value > 0 else 0
        
        # 총 투자금 대비 총 평가액의 누적 수익률
        total_all_time_return = ((total_value - total_invested) / total_invested) * 100 if total_invested > 0 else 0
        
        # 메인 지표 출력 (오늘의 변동과 누적 손익을 두 칸으로 나누어 보여줌!)
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label="총 자산 평가액 (USD)", 
                value=f"${total_value:,.2f}",
                delta=f"오늘의 변동: {total_daily_change:,.2f} ({total_change_percent:.2f}%)"
            )
        with col2:
            st.metric(
                label="총 누적 수익률", 
                value=f"{total_all_time_return:.2f}%",
                delta=f"총 누적 손익: ${(total_value - total_invested):,.2f}"
            )
        
        st.divider()
        
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="비중", ascending=False).reset_index(drop=True)
            
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "종목": st.column_config.TextColumn("종목명"),
                    "보유 수량": st.column_config.NumberColumn("수량", format="%.2f"),
                    "평단가": st.column_config.NumberColumn("평단가 ($)", format="$%.2f"),
                    "현재가": st.column_config.NumberColumn("현재가 ($)", format="$%.2f"),
                    "수익률": st.column_config.NumberColumn("누적 수익률 (%)", format="%.2f%%"),
                    "평가액": st.column_config.NumberColumn("평가액 ($)", format="$%.2f"),
                    "비중": st.column_config.ProgressColumn(
                        "비중 (%)",
                        format="%.2f%%",
                        min_value=0,
                        max_value=100,
                    ),
                }
            )

st.caption("데이터 출처: Yahoo Finance / 매매 장부: 구글 스프레드시트 연동")

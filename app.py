import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="한결 포트폴리오", layout="wide")

st.title("📊 자산관리 대시보드")
st.write("실시간 주가와 내 보유 수량을 곱해 총 자산과 수익률을 계산합니다.")

portfolio = {
    'VOO': 1.0,
    'SPCX': 3.0,
    'SGOV': 3.0,
    'NEE': 3.0,
    'IBM': 1.0,
    'KO': 2.0,
    'RGTI': 9.0,
    'ARQQ': 7.0,
    'BAC': 2.0,
    'LMT': 0.16,
    'GOOGL': 1.23
}

st.subheader("💰 실시간 내 자산 현황")

with st.spinner('실시간 자산 가치와 오늘의 수익률을 계산하는 중입니다...'):
    total_value = 0.0
    total_daily_change = 0.0
    results = []
    
    # 1차 계산: 총 자산 먼저 구하기
    for ticker, shares in portfolio.items():
        try:
            stock_data = yf.Ticker(ticker).history(period="5d", prepost=True)
            if len(stock_data) >= 2:
                current_price = stock_data['Close'].iloc[-1]
                prev_close = stock_data['Close'].iloc[-2]
                
                value = current_price * shares
                change_dollar = (current_price - prev_close) * shares
                change_percent = ((current_price - prev_close) / prev_close) * 100
                
                total_value += value
                total_daily_change += change_dollar
                
                results.append({
                    "종목": ticker,
                    "보유 수량": shares,
                    "현재가": current_price,
                    "오늘의 변동": change_dollar,
                    "등락률": change_percent,
                    "평가액": value
                })
        except Exception:
            pass
            
    # 2차 계산: 구해진 총 자산을 바탕으로 각 종목의 퍼센트(비중) 계산하기
    for row in results:
        row["비중"] = (row["평가액"] / total_value) * 100 if total_value > 0 else 0
            
    base_value = total_value - total_daily_change
    total_change_percent = (total_daily_change / base_value) * 100 if base_value > 0 else 0
    
    st.metric(
        label="총 자산 평가액 (USD)", 
        value=f"${total_value:,.2f}",
        delta=f"{total_daily_change:,.2f} ({total_change_percent:.2f}%)"
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
                "보유 수량": st.column_config.NumberColumn("수량 (주)", format="%.2f"),
                "현재가": st.column_config.NumberColumn("현재가 ($)", format="$%.2f"),
                "오늘의 변동": st.column_config.NumberColumn("오늘 변동액 ($)", format="$%.2f"),
                "등락률": st.column_config.NumberColumn("등락률 (%)", format="%.2f%%"),
                "평가액": st.column_config.NumberColumn("평가액 ($)", format="$%.2f"),
                # 새로운 비중(%) 컬럼에 숫자와 막대그래프를 동시 적용!
                "비중": st.column_config.ProgressColumn(
                    "비중 (%)",
                    help="내 총 자산 대비 해당 종목의 비율",
                    format="%.2f%%",
                    min_value=0,
                    max_value=100,
                ),
            }
        )

st.caption("데이터 출처: Yahoo Finance (프리/애프터마켓 반영)")

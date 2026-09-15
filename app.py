import streamlit as st
import yfinance as yf

st.set_page_config(page_title="한결 포트폴리오", layout="wide")

st.title("📊 자산관리 대시보드")
st.write("종목을 자유롭게 추가하거나 삭제하여 주가를 확인하세요.")

# 앱 화면에서 직접 종목을 수정할 수 있는 입력창 생성
default_tickers = "VOO, SPCX, SGOV, NEE, IBM, KO, RGTI, ARQQ, BAC, LMT, GOOGL"
user_input = st.text_input("조회할 종목 (쉼표로 구분하여 입력)", value=default_tickers)

# 입력된 문자열을 리스트로 변환
tickers = [t.strip().upper() for t in user_input.split(',') if t.strip()]

st.subheader("현재가 확인 (프리/애프터마켓 포함)")

if tickers:
    with st.spinner('주가를 불러오는 중입니다...'):
        cols = st.columns(3)
        
        for i, ticker in enumerate(tickers):
            try:
                # ★ 핵심 업그레이드: prepost=True 옵션을 넣어서 프리/애프터 마켓 가격을 가져옵니다.
                stock_data = yf.Ticker(ticker).history(period="1d", prepost=True)
                
                if not stock_data.empty:
                    current_price = stock_data['Close'].iloc[-1]
                    with cols[i % 3]:
                        st.metric(label=ticker, value=f"${current_price:.2f}")
                else:
                    with cols[i % 3]:
                        st.metric(label=ticker, value="데이터 없음")
            except Exception:
                with cols[i % 3]:
                    st.metric(label=ticker, value="오류")
else:
    st.info("조회할 종목 기호를 입력해 주세요.")

st.caption("데이터 출처: Yahoo Finance (프리/애프터마켓 반영)")

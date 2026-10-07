import streamlit as st
import datetime
import config
import data_engine
import ui_components

# ==========================================
# 페이지 기본 설정
# ==========================================
st.set_page_config(layout="wide", page_title="맞춤형 자산관리 대시보드", page_icon="📊")

# ==========================================
# 1. 사이드바: 데이터 입력 관제탑 (현금흐름 추가 완비)
# ==========================================
with st.sidebar:
    st.header("📝 거래 및 현금흐름 기록")
    
    # 3개의 탭으로 분리 (환전/입출금 추가)
    tab_trade, tab_div, tab_fx = st.tabs(["📈 매매 기록", "💰 배당 기록", "💵 환전/입출금"])
    
    # [탭 1] 매매 기록
    with tab_trade:
        with st.form("trade_form", clear_on_submit=True):
            st.markdown("### 📈 주식 매매 기록")
            t_date = st.date_input("매매 일자", datetime.date.today())
            t_ticker = st.text_input("티커 (예: VOO)")
            t_type = st.selectbox("거래 종류", ["매수", "매도"])
            t_price = st.number_input("체결 단가 ($)", min_value=0.0, format="%.2f")
            t_shares = st.number_input("수량 (주)", min_value=0.0, format="%.4f")
            t_fx = st.number_input("적용 환율 (원)", min_value=0.0, format="%.2f")
            
            if st.form_submit_button("매매 기록 저장"):
                # 향후 data_engine.py 구글 시트 연동 함수 호출 (현재는 UI 껍데기)
                st.success(f"{t_ticker} {t_type} 기록 완료! (엔진 연동 대기중)")
                st.rerun()

    # [탭 2] 배당 기록
    with tab_div:
        with st.form("dividend_form", clear_on_submit=True):
            st.markdown("### 💰 배당금 수령 기록")
            d_date = st.date_input("수령 일자", datetime.date.today())
            d_ticker = st.text_input("티커 (예: SCHD)")
            d_amount = st.number_input("세후 배당금 ($)", min_value=0.0, format="%.2f")
            
            if st.form_submit_button("배당 기록 저장"):
                st.success(f"{d_ticker} 배당금 ${d_amount} 기록 완료! (엔진 연동 대기중)")
                st.rerun()

    # [탭 3] 환전 및 입출금 기록 (신설)
    with tab_fx:
        with st.form("fx_form", clear_on_submit=True):
            st.markdown("### 💵 달러 현금흐름 기록")
            st.info("➕ 입금: 원화 -> 달러 환전 (달러 예수금 증가)\n\n➖ 출금: 달러 -> 원화 환전 (달러 감소 및 수익 락인)")
            
            fx_date = st.date_input("날짜", datetime.date.today())
            fx_type = st.selectbox("거래 분류", ["달러 입금(환전 매수)", "달러 출금(환전 매도)"])
            fx_usd_amount = st.number_input("달러 금액 ($)", min_value=0.0, step=10.0, format="%.2f")
            fx_rate = st.number_input("적용 환율 (원)", min_value=0.0, step=1.0, format="%.2f")
            
            if st.form_submit_button("환전/입출금 기록 저장"):
                st.success(f"{fx_type} ${fx_usd_amount:,.2f} 기록 완료! (엔진 연동 대기중)")
                st.rerun()

# ==========================================
# 2. 메인 대시보드 렌더링
# ==========================================
def main():
    st.title("📊 Multi-Currency 포트폴리오 대시보드")
    
    # 데이마켓 상태 등 마켓 정보 표시 (ui_components 모듈 호출)
    ui_components.render_market_status()
    
    st.markdown("---")
    
    # 데이터 엔진에서 통합 데이터 로드 (시트 내역 + 실시간 시세 + 환율)
    # 현재 엔진 연동 전이므로 임시 홀더 처리
    with st.spinner("데이터 엔진을 가동하여 포트폴리오를 구성 중입니다..."):
        try:
            portfolio_data = data_engine.load_all_data()
        except Exception as e:
            st.warning("데이터 엔진(data_engine.py)이 아직 V6.1 규격으로 업데이트되지 않았습니다. 백엔드 업데이트를 진행해주세요.")
            return

    if not portfolio_data:
        st.info("표시할 포트폴리오 데이터가 없습니다.")
        return

    # 핵심 성과표 렌더링 (Row 1 & Row 2: 4칸짜리 무결점 패널)
    ui_components.render_performance_summary(portfolio_data)
    
    # 개별 종목 상세 테이블 및 특징주 브리핑 렌더링
    ui_components.render_portfolio_table(portfolio_data)

if __name__ == "__main__":
    main()

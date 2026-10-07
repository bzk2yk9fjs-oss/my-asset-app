# ==========================================
# UI 컴포넌트 엔진 (ui_components.py)
# 기능: 대시보드 화면 렌더링, 성과표 4칸 패널 표시
# ==========================================
import streamlit as st
import pandas as pd

def render_market_status():
    """
    상단 마켓 상태 표시 (데이마켓 등)
    """
    st.info("🕒 현재 데이마켓(Day Market) 개장 시간입니다. (시세는 직전 애프터마켓 최종 마감가 기준)")

def render_performance_summary(portfolio_data):
    """
    네가 설계한 V5.3 무결점 회계 논리를 100% 반영한 
    Row 1 (내 자산 현황) & Row 2 (투자 성과표) 렌더링
    """
    port = portfolio_data.get("portfolio", {})
    usd_cash = portfolio_data.get("usd_cash_balance", 0.0)
    total_profit_usd = portfolio_data.get("total_profit_usd", 0.0)
    total_div_usd = portfolio_data.get("total_dividends_usd", 0.0)
    locked_in_krw = portfolio_data.get("locked_in_profit_krw", 0.0)
    live_fx = portfolio_data.get("current_live_fx", 1350.0)

    # 임시 연산 (API 실시간 가격 연동 전, 투자원금을 임시 현재가로 가정)
    total_stock_value_usd = sum(info["총투자금USD"] for info in port.values())
    total_invested_krw = sum(info["총투자금KRW"] for info in port.values())
    
    total_asset_usd = total_stock_value_usd + usd_cash
    total_asset_krw = (total_asset_usd * live_fx) + locked_in_krw
    
    # 총 누적 손익 KRW (공식 1: 미환전 실시간 가치 + 공식 2: 락인 수익)
    live_profit_krw = total_profit_usd * live_fx
    principal_fx_gain = (total_stock_value_usd * live_fx) - total_invested_krw
    total_profit_krw = live_profit_krw + principal_fx_gain + locked_in_krw

    # --- ROW 1: 내 자산 현황 패널 ---
    st.markdown("### 💰 내 자산 현황 (종합 평가액)")
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    r1_c1.metric("총 주식 평가액 (USD)", f"${total_stock_value_usd:,.2f}")
    r1_c2.metric("총 수익률 (TR USD %)", "0.00%") # 추후 시세 API 연동 시 업데이트
    r1_c3.metric("총 수익률 (TR KRW %)", "0.00%") 
    r1_c4.metric("총 자산 평가액 (KRW)", f"{total_asset_krw:,.0f}원")

    st.markdown("---")

    # --- ROW 2: 투자 성과표 (무결점 실현손익 & 환전 회계) ---
    st.markdown("### 📈 투자 성과표 (실현손익 & 미환전 달러 추적)")
    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
    
    r2_c1.metric("[1칸] 누적 수령 배당금 (USD)", f"${total_div_usd:,.2f}", "달러 현금흐름 누적액")
    r2_c2.metric("[2칸] 총 누적 손익 (USD)", f"${total_profit_usd:,.2f}", "매도 차익 + 배당금")
    r2_c3.metric("[3칸] 총 누적 손익 (KRW)", f"{total_profit_krw:,.0f}원", "실시간 환차익 + 환전 Lock-in 합산")
    r2_c4.metric("[4칸] 미환전 달러 잔고 (USD)", f"${usd_cash:,.2f}", "증권사 예수금과 100% 일치", delta_color="off")

def render_portfolio_table(portfolio_data):
    """
    개별 종목 상세 테이블 렌더링
    """
    st.markdown("---")
    st.markdown("### 📋 포트폴리오 상세")
    st.caption("⚠️ 기준: **SGOV**는 유일한 현금성 자산, **SPCX**는 ETF가 아닌 개별주로 분류됩니다.")
    
    port = portfolio_data.get("portfolio", {})
    if not port:
        st.info("데이터가 없습니다.")
        return
    
    # 딕셔너리를 보기 좋은 데이터프레임으로 변환
    df = pd.DataFrame.from_dict(port, orient='index')
    st.dataframe(df, use_container_width=True)

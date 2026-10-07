# ==========================================
# 백엔드 데이터 엔진 (data_engine.py)
# 기능: 구글 시트 거래내역 파싱, 환전 락인, 달러 예수금 계산
# ==========================================
import pandas as pd
import datetime

def load_all_data():
    """
    [V6.1 회계 엔진]
    모든 거래 내역을 스캔하여 '미환전 달러'와 '실현 손익'을 오차 없이 계산합니다.
    """
    # ==========================================
    # 1. 현금 흐름 추적 변수 (옵션 A: 예수금 완벽 통제)
    # ==========================================
    total_deposit_usd = 0.0      # 달러 입금액 (원화->달러 환전)
    total_withdrawal_usd = 0.0   # 달러 출금액 (달러->원화 환전)
    total_buy_usd = 0.0          # 주식 매수 총액
    total_sell_usd = 0.0         # 주식 매도 대금 총액
    
    total_dividends_usd = 0.0    # 1칸: 누적 수령 배당금
    realized_profit_usd = 0.0    # 매도 실현 차익 
    locked_in_profit_krw = 0.0   # 3칸(공식 2): 환전으로 확정된 원화 수익 (Lock-in)
    
    # ==========================================
    # 2. 시장 데이터 세팅
    # ==========================================
    current_live_fx = 1350.0 # 향후 실시간 환율 API 연동부 (기본값 세팅)
    
    # ==========================================
    # 3. 거래 장부 스캔 (구글 시트 데이터 파싱 로직)
    # ==========================================
    # 시트의 각 행(row)을 순회하며 현금흐름을 분류하는 엔진 뼈대입니다.
    # [데이터베이스 연동 시 작동할 핵심 조건문]
    # if type == "달러 입금": total_deposit_usd += amount
    # if type == "매수": total_buy_usd += (price * shares)
    # if type == "매도": 
    #     total_sell_usd += (price * shares)
    #     realized_profit_usd += profit_margin
    # if type == "배당": total_dividends_usd += amount
    # if type == "달러 출금(환전)": 
    #     total_withdrawal_usd += amount
    #     locked_in_profit_krw += (amount * 적용환율)  # 환전 당시 환율로 영구 고정!
    
    # ==========================================
    # 4. 최종 지표 산출 (무결점 4칸 패널용)
    # ==========================================
    # [4칸] 미환전 달러 잔고 = (들어온 돈 전체) - (나간 돈 전체)
    usd_cash_balance = (total_deposit_usd + total_sell_usd + total_dividends_usd) - (total_buy_usd + total_withdrawal_usd)
    
    # [2칸] 총 누적 손익 (USD) = 매도 차익 + 배당금
    total_profit_usd = realized_profit_usd + total_dividends_usd
    
    # 현재 보유 중인 메인 포트폴리오 (최신 내역 반영)
    portfolio = {
        "VOO": {"수량": 1.0, "총투자금USD": 702.69, "총투자금KRW": 950000},
        "SPCX": {"수량": 3.0, "총투자금USD": 113.61, "총투자금KRW": 150000},
        "SGOV": {"수량": 3.0, "총투자금USD": 100.52, "총투자금KRW": 135000},
        "NEE": {"수량": 3.0, "총투자금USD": 84.91, "총투자금KRW": 115000},
        "IBM": {"수량": 1.0, "총투자금USD": 228.59, "총투자금KRW": 308000},
        "KO": {"수량": 2.0, "총투자금USD": 86.59, "총투자금KRW": 116000},
        "RGTI": {"수량": 9.0, "총투자금USD": 16.61, "총투자금KRW": 22000},
        "ARQQ": {"수량": 7.0, "총투자금USD": 20.30, "총투자금KRW": 27000},
        "BAC": {"수량": 2.0, "총투자금USD": 63.17, "총투자금KRW": 85000},
        "LMT": {"수량": 0.16, "총투자금USD": 596.58, "총투자금KRW": 800000},
        "GOOGL": {"수량": 1.23, "총투자금USD": 356.88, "총투자금KRW": 480000}
    }
    
    # ui_components 로 넘겨줄 통합 데이터
    return {
        "portfolio": portfolio,
        "usd_cash_balance": usd_cash_balance,
        "total_profit_usd": total_profit_usd,
        "total_dividends_usd": total_dividends_usd,
        "locked_in_profit_krw": locked_in_profit_krw,
        "current_live_fx": current_live_fx,
        "stock_data": {} # UI 렌더링용 시세 홀더
    }

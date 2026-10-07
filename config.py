# config.py

# ==========================================
# 0. 스마트 한글 사전 (Portfolio & Major US Stocks)
# ==========================================
KOR_NAMES = {
    'VOO': '뱅가드 S&P 500', 'SGOV': '미국 0-3개월 초단기채', 'KO': '코카콜라', 
    'BAC': '뱅크오브아메리카', 'NEE': '넥스트에라 에너지', 'LMT': '록히드 마틴', 
    'GOOGL': '알파벳 A', 'IBM': 'IBM', 'SPCX': '스페이스X', 
    'RGTI': '리게티 컴퓨팅', 'ARQQ': '아킷 퀀텀',
    'AAPL': '애플', 'MSFT': '마이크로소프트', 'AMZN': '아마존닷컴', 'NVDA': '엔비디아', 
    'TSLA': '테슬라', 'META': '메타 플랫폼스', 'BRK.B': '버크셔 해서웨이', 'AVGO': '브로드컴', 
    'TSM': 'TSMC', 'LLY': '일라이 릴리', 'JPM': 'JP모건 체이스', 'V': '비자', 
    'XOM': '엑슨모빌', 'UNH': '유나이티드헬스', 'PG': '프록터 앤 갬블 (P&G)', 
    'MA': '마스터카드', 'JNJ': '존슨앤존슨', 'HD': '홈디포', 'MRK': '머크', 'CVX': '쉐브론',
    'SPY': 'SPDR S&P 500', 'QQQ': '인베스코 QQQ', 'DIA': 'SPDR 다우존스',
    'SCHD': '슈왑 배당 ETF (SCHD)', 'JEPI': 'JP모건 커버드콜 (JEPI)', 'TLT': '미국 20년 이상 장기채',
    'TQQQ': '프로셰어즈 TQQQ (나스닥 3X)', 'SQQQ': '프로셰어즈 SQQQ (인버스 3X)', 
    'SOXL': '디렉시온 SOXL (반도체 3X)', 'SOXS': '디렉시온 SOXS (인버스 3X)',
    'SSO': '프로셰어즈 SSO (S&P 500 2X)', 'UPRO': '프로셰어즈 UPRO (S&P 500 3X)',
    'QLD': '프로셰어즈 QLD (나스닥 2X)', 'SOXX': 'iShares 반도체 ETF', 'USD': '프로셰어즈 반도체 2X',
    'SNXX': '트레이더 샌디스크 2X', 'NVDL': '그래니트셰어즈 엔비디아 2X', 
    'TSLL': '디렉시온 테슬라 1.5X', 'CONL': '그래니트셰어즈 코인베이스 2X',
    'LEU': '센트러스 에너지'
}

def normalize_category(cat):
    """자산군 카테고리 이름을 규격화하는 함수"""
    cat_str = str(cat).strip()
    if '코어' in cat_str: return '코어 (Core)'
    if '방어' in cat_str: return '방어 (Defensive)'
    if '우량' in cat_str: return '우량주 (Blue Chip)'
    if '모험' in cat_str: return '모험주 (Adventure)'
    if '모멘텀' in cat_str: return '모멘텀 (Momentum)'
    return '기타 (Others)'

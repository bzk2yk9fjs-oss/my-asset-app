import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components

# ==========================================
# 1. 텍스트 컬러 변환 (UI 유틸리티 내장)
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

def get_macro_color_text(val, is_percent=True, prefix="", suffix=""):
    if pd.isna(val) or val is None: return ":gray[데이터 없음]"
    sign = "+" if val > 0 else ""
    fmt = f"{val:.2f}"
    if is_percent: res = f"{sign}{fmt}%"
    else: res = f"{sign}{prefix}{abs(val):.2f}{suffix}"
    if val > 0: return f":red[{res}]"
    elif val < 0: return f":blue[{res}]"
    else: return f":gray[{res}]"


# ==========================================
# 2. UI 렌더링 부품들
# ==========================================
def render_summary(total_value_usd, price_basis_label, total_daily_change_usd, change_label,
                   total_dividend_usd_all, total_all_time_usd_tr, total_profit_usd_only,
                   total_return_krw_tr, total_profit_krw_tr, total_value_krw, total_fx_gain_loss_krw):
    st.subheader("💰 계좌 총괄 요약 (Total Summary)")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(label=f"평가액(USD)-[{price_basis_label}]", value=f"${total_value_usd:,.2f}", delta=f"{total_daily_change_usd:,.2f} USD ({change_label})")
    col2.metric(label="누적 배당금(USD)", value=f"${total_dividend_usd_all:,.2f}", delta="현금흐름 확보", delta_color="normal")
    col3.metric(label="총수익률(TR USD)", value=f"{total_all_time_usd_tr:+.2f}%", delta=f"{(total_profit_usd_only + total_dividend_usd_all):,.2f} USD (손익+배당)")
    col4.metric(label="총수익률(TR KRW)", value=f"{total_return_krw_tr:+.2f}%", delta=f"{int(total_profit_krw_tr):,} 원 (주식+배당+환차)")
    col5.metric(label="평가액(KRW)", value=f"{int(total_value_krw):,} 원", delta=f"총 환차손익: {int(total_fx_gain_loss_krw):,} 원", delta_color="normal")
    st.divider()

def render_portfolio_table(results):
    df = pd.DataFrame(results).sort_values(by="비중", ascending=False).reset_index(drop=True)
    st.subheader("📊 포트폴리오 상세 (주식 성과 및 누적 배당 분리)")
    
    fig = px.pie(df, values='평가액 ($)', names='그룹', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={"티커": "티커", "종목명": "종목명", "그룹": "자산군", 
                                "보유 수량": st.column_config.NumberColumn("수량", format="%.4f"),
                                "평단가 ($)": st.column_config.NumberColumn("평단가($)", format="$%.2f"),
                                "현재가 ($)": st.column_config.NumberColumn("현재가($)", format="$%.2f"),
                                "매입환율": st.column_config.NumberColumn("매입환율", format="%.2f"),
                                "누적배당($)": st.column_config.NumberColumn("누적배당($)", format="$%.2f"),
                                "주가수익(%)": st.column_config.NumberColumn("단순주가(%)", format="%.2f%%"),
                                "당일 변동 (%)": st.column_config.NumberColumn("당일변동(%)", format="%.2f%%"),
                                "환차손익(KRW)": st.column_config.NumberColumn("환차손익(원)"),
                                "평가액 ($)": st.column_config.NumberColumn("평가액($)", format="$%.2f"),
                                "비중": st.column_config.ProgressColumn("비중(%)", format="%.2f%%", min_value=0, max_value=100)})
    st.divider()
    return df

def render_analysis_report(yesterday_recap, sp500_change, last_closed_date_str, df, is_market_closed, m_state, now_kr):
    st.header("📰 시황 분석 리포트 (투트랙)")
    st.subheader(f"🌙 1. 전일장 마감 요약 (미국시간 {last_closed_date_str} 정규장 마감 기준)")
    
    if yesterday_recap:
        df_y = pd.DataFrame(yesterday_recap)
        tot_dby = df_y['그제가치'].sum()
        tot_y = df_y['어제가치'].sum()
        tot_chg_dollar = tot_y - tot_dby
        tot_chg_pct = (tot_chg_dollar / tot_dby * 100) if tot_dby > 0 else 0.0
        outperform = tot_chg_pct - sp500_change
        
        st.markdown(f"**📌 계좌 총괄 성적:** 전일 대비 **{get_color_text(tot_chg_pct)}** ({get_color_text(tot_chg_dollar, False)})")
        st.write(f"👉 시장(S&P 500: {get_color_text(sp500_change)}) 대비 **{abs(outperform):.2f}%p {'상회' if outperform > 0 else '하회'}**")
        
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
            top, btm = valid_df_y.loc[valid_df_y['어제변동률'].idxmax()], valid_df_y.loc[valid_df_y['어제변동률'].idxmin()]
            c1, c2 = st.columns(2)
            with c1: st.success(f"🚀 **최고 효자:** {top['종목']} ({get_color_text(top['어제변동률'])})")
            with c2: st.error(f"📉 **최대 구멍:** {btm['종목']} ({get_color_text(btm['어제변동률'])})")
            
    st.write("") 
    st.subheader("⚡ 2. 실 실시간 흐름 파악 (당일 라이브)")
    if is_market_closed or m_state.startswith("⚪"): 
        st.info("💡 프리마켓 개장 전(또는 데이마켓 진행 중)이므로 실시간 급변동 감지가 비활성화됩니다.")
    else:
        active_df = df[df['당일 변동 (%)'] != 0.0]
        if len(active_df) > 0:
            top_mover = active_df.loc[active_df['당일 변동 (%)'].abs().idxmax()]
            if abs(top_mover['당일 변동 (%)']) >= 3.0:
                st.error(f"🚨 **[특징주 감지]** 현재 **{top_mover['종목명']}({top_mover['티커']})** 종목이 **{get_color_text(top_mover['당일 변동 (%)'])}** 급변동 중입니다.")
                
                prompt_text = (
                    f"[{now_kr.strftime('%Y년 %m월 %d일 %H:%M')} KST 기준]\n"
                    f"내 포트폴리오의 [{top_mover['티커']}] 종목이 {top_mover['당일 변동 (%)']:+.2f}% 급변동 중이다.\n"
                    f"외신 및 공시를 기반으로 원인과 대응책을 분석하되, 반드시 다음 프로세스를 거쳐서 답변해라:\n"
                    f"1단계: 실시간 가격 확인\n"
                    f"2단계: 뉴스 매칭\n"
                    f"3단계: 정합성 검증"
                )
                st.code(prompt_text, language="markdown")
            else: 
                st.success("✔️ 기준치(±3%)를 초과하는 실시간 급변동 종목이 없습니다.")

def render_macro_tab(krw, tnx, wti):
    st.subheader("🌍 매크로 경제 지표 종합 대시보드")
    st.markdown("### 1. S&P 500 섹터 히트맵")
    components.html('''<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>{"exchanges": [],"dataSource": "SPX500","grouping": "sector","blockSize": "market_cap_basic","blockColor": "change","locale": "kr","colorTheme": "light","hasTopBar": false,"isDataSetEnabled": false,"isZoomEnabled": true,"hasSymbolTooltip": true,"width": "100%","height": "500"}</script></div>''', height=500)
    st.divider()
    
    st.markdown("### 2. 핵심 매크로 지표 (실시간 숫자 뷰)")
    mac1, mac2, mac3 = st.columns(3)
    with mac1:
        with st.container(border=True):
            st.markdown("**🇺🇸 USD/KRW 환율**")
            st.markdown(f"### {krw['live']:,.2f} 원")
            st.markdown(f"**전일 대비: {get_macro_color_text(krw['change'], False, suffix='원')} ({get_macro_color_text(krw['pct'], True)})**")
    with mac2:
        with st.container(border=True):
            st.markdown("**미국 10년물 국채 금리**")
            st.markdown(f"### {tnx['live']:.3f} %")
            st.markdown(f"**전일 대비: {get_macro_color_text(tnx['change'], False, suffix='%p')} ({get_macro_color_text(tnx['pct'], True)})**")
    with mac3:
        with st.container(border=True):
            st.markdown("**🛢️ WTI 원유 (선물)**")
            st.markdown(f"### ${wti['live']:.2f}")
            st.markdown(f"**전일 대비: {get_macro_color_text(wti['change'], False, prefix='$')} ({get_macro_color_text(wti['pct'], True)})**")
    st.divider()
    
    st.markdown("### 3. 시장 심리 및 금리 예측 지표")
    st.markdown("👉 **[🔗 CNN Fear & Greed Index 실시간 확인하기 (클릭)](https://edition.cnn.com/markets/fear-and-greed)**")
    st.markdown("👉 **[🔗 CME FedWatch Tool (금리 인상 확률) 확인하기 (클릭)](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)**")

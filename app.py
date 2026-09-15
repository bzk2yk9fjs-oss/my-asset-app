    with tab2:
        # --- 매크로 지표 상황판 ---
        st.subheader("🌍 매크로 경제 지표 종합 대시보드")
        
        st.markdown("### 1. S&P 500 섹터 히트맵 (TradingView)")
        st.write("미국 증시 전반의 붉고 푸른 흐름을 직관적으로 확인하세요.")
        
        # 핀비즈 대신 트레이딩뷰 공식 위젯으로 교체! (하얗게 뜨는 오류 해결)
        components.html(
            """
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
            """, height=500
        )
        
        st.divider()
        st.markdown("### 2. Fear and Greed Index (공포와 탐욕 지수)")
        st.write("현재 시장 참여자들의 심리 상태를 보여줍니다.")
        # 앱 안에 바로 띄우기
        components.iframe("https://edition.cnn.com/markets/fear-and-greed", height=500, scrolling=True)
        
        st.divider()
        st.markdown("### 3. CME FedWatch Tool (금리 예측)")
        st.write("미 연준(Fed)의 다음 기준금리 결정 확률을 실시간으로 추적합니다.")
        # 앱 안에 바로 띄우기
        components.iframe("https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html", height=500, scrolling=True)

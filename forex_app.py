#!/usr/bin/env python3
"""
Forex Analyzer Mobile App
=========================
A clean, phone-friendly Streamlit dashboard for live Forex analysis.

How to run locally:
    pip install streamlit biquote pandas numpy ta plotly
    streamlit run forex_app.py

Then open the local URL on your phone (same Wi-Fi) or deploy free to Streamlit Cloud.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

try:
    from biquote import Biquote
except ImportError:
    st.error("Please install: pip install biquote")
    st.stop()

try:
    import ta
except ImportError:
    st.error("Please install: pip install ta")
    st.stop()

# -------------------- Page Config (mobile friendly) --------------------
st.set_page_config(
    page_title="Forex Analyzer",
    page_icon="💱",
    layout="centered",          # better for phones
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile look
st.markdown("""
<style>
    .stApp {
        max-width: 480px;
        margin: 0 auto;
    }
    .metric-card {
        background: #1e1e2f;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 10px;
        border: 1px solid #2d2d44;
    }
    .signal-buy { color: #00c853; font-weight: 700; }
    .signal-sell { color: #ff5252; font-weight: 700; }
    .signal-neutral { color: #b0b0b0; font-weight: 600; }
    .big-price { font-size: 1.6rem; font-weight: 700; }
    .small { font-size: 0.85rem; color: #aaa; }
    h1 { text-align: center; font-size: 1.6rem !important; }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3rem;
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)

# -------------------- Config --------------------
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
    "EURJPY", "GBPJPY", "XAUUSD"
]

bq = Biquote()

# -------------------- Helper functions --------------------
@st.cache_data(ttl=60)  # cache 60 seconds
def get_tick(symbol: str):
    try:
        return bq.tick(symbol)
    except Exception:
        return None

@st.cache_data(ttl=120)
def get_ohlc(symbol: str, interval: str = "1h", limit: int = 100):
    try:
        data = bq.ohlc(symbol, interval=interval, limit=limit)
        if not data:
            return None
        df = pd.DataFrame(data)
        df["openTime"] = pd.to_datetime(df["openTime"])
        df = df.sort_values("openTime").reset_index(drop=True)
        df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "tickVolume": "Volume"
        }, inplace=True)
        return df
    except Exception:
        return None

def analyze(symbol: str):
    result = {
        "symbol": symbol,
        "mid": None,
        "day_pct": None,
        "rsi": None,
        "trend_1h": "—",
        "trend_4h": "—",
        "ma_signal": "—",
        "macd_signal": "—",
        "signal": "NEUTRAL",
        "strength": 0.0,
        "summary": ""
    }

    tick = get_tick(symbol)
    if not tick:
        return result

    result["mid"] = tick.get("mid")
    result["day_pct"] = tick.get("dayDiffPercent")
    result["bid"] = tick.get("bid")
    result["ask"] = tick.get("ask")
    result["spread"] = tick.get("spread")

    df = get_ohlc(symbol, "1h", 100)
    if df is not None and len(df) > 40:
        close = df["Close"]

        # RSI
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        result["rsi"] = round(float(rsi_series.iloc[-1]), 1)

        # MAs
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        last = close.iloc[-1]
        if last > sma20.iloc[-1] > sma50.iloc[-1]:
            result["ma_signal"] = "BULLISH"
            result["trend_1h"] = "UP"
        elif last < sma20.iloc[-1] < sma50.iloc[-1]:
            result["ma_signal"] = "BEARISH"
            result["trend_1h"] = "DOWN"
        else:
            result["ma_signal"] = "MIXED"
            result["trend_1h"] = "SIDE"

        # MACD
        macd = ta.trend.MACD(close)
        if macd.macd().iloc[-1] > macd.macd_signal().iloc[-1]:
            result["macd_signal"] = "BULLISH"
        else:
            result["macd_signal"] = "BEARISH"

    # 4h trend
    df4 = get_ohlc(symbol, "4h", 40)
    if df4 is not None and len(df4) > 20:
        close4 = df4["Close"]
        sma20_4 = close4.rolling(20).mean()
        result["trend_4h"] = "UP" if close4.iloc[-1] > sma20_4.iloc[-1] else "DOWN"

    # Scoring
    score = 0.0
    reasons = []

    if result["rsi"] is not None:
        if result["rsi"] <= 30:
            score += 2.0
            reasons.append(f"RSI oversold ({result['rsi']})")
        elif result["rsi"] >= 70:
            score -= 2.0
            reasons.append(f"RSI overbought ({result['rsi']})")
        elif result["rsi"] < 45:
            score += 0.5
        elif result["rsi"] > 55:
            score -= 0.5

    if result["ma_signal"] == "BULLISH":
        score += 1.5
        reasons.append("MA bullish")
    elif result["ma_signal"] == "BEARISH":
        score -= 1.5
        reasons.append("MA bearish")

    if result["macd_signal"] == "BULLISH":
        score += 1.0
        reasons.append("MACD bullish")
    elif result["macd_signal"] == "BEARISH":
        score -= 1.0
        reasons.append("MACD bearish")

    if result["trend_4h"] == "UP":
        score += 0.5
    elif result["trend_4h"] == "DOWN":
        score -= 0.5

    result["strength"] = round(score, 1)

    if score >= 2.5:
        result["signal"] = "STRONG BUY"
    elif score >= 1.0:
        result["signal"] = "BUY"
    elif score <= -2.5:
        result["signal"] = "STRONG SELL"
    elif score <= -1.0:
        result["signal"] = "SELL"
    else:
        result["signal"] = "NEUTRAL"

    result["summary"] = " • ".join(reasons) if reasons else "No strong confluence"
    return result

def signal_class(sig: str) -> str:
    if "BUY" in sig:
        return "signal-buy"
    if "SELL" in sig:
        return "signal-sell"
    return "signal-neutral"

# -------------------- UI --------------------
st.title("💱 Forex Analyzer")
st.caption(f"Live data • Updated {datetime.now(timezone.utc).strftime('%H:%M UTC')}")

# Refresh button
col1, col2 = st.columns([3, 1])
with col1:
    auto = st.toggle("Auto-refresh every 60s", value=False)
with col2:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Main pairs overview
st.subheader("Market Overview")

# Analyze all pairs
analyses = []
progress = st.progress(0)
for i, pair in enumerate(PAIRS):
    analyses.append(analyze(pair))
    progress.progress((i + 1) / len(PAIRS))
progress.empty()

# Sort: strongest signals first
analyses.sort(key=lambda x: abs(x["strength"]), reverse=True)

# Display as cards
for a in analyses:
    mid = a["mid"]
    if mid is None:
        continue

    day = a["day_pct"] or 0.0
    day_color = "#00c853" if day >= 0 else "#ff5252"
    sig_class = signal_class(a["signal"])

    price_str = f"{mid:.5f}" if mid < 10 else f"{mid:.3f}"

    st.markdown(f"""
    <div class="metric-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="font-size:1.1rem; font-weight:600;">{a['symbol']}</div>
                <div class="big-price">{price_str}</div>
                <div class="small" style="color:{day_color};">{day:+.2f}% today</div>
            </div>
            <div style="text-align:right;">
                <div class="{sig_class}" style="font-size:1.05rem;">{a['signal']}</div>
                <div class="small">Strength {a['strength']:+.1f}</div>
                <div class="small">RSI {a['rsi'] if a['rsi'] else '—'}</div>
            </div>
        </div>
        <div class="small" style="margin-top:8px;">
            1H: {a['trend_1h']} &nbsp;|&nbsp; 4H: {a['trend_4h']} &nbsp;|&nbsp; {a['summary']}
        </div>
    </div>
    """, unsafe_allow_html=True)

# Detailed view
st.divider()
st.subheader("Detailed View")
selected = st.selectbox("Choose pair for more details", PAIRS, index=0)

detail = next((a for a in analyses if a["symbol"] == selected), None)
if detail and detail["mid"]:
    c1, c2, c3 = st.columns(3)
    c1.metric("Price", f"{detail['mid']:.5f}")
    c2.metric("Day Change", f"{detail['day_pct']:+.2f}%" if detail["day_pct"] is not None else "—")
    c3.metric("RSI (14)", detail["rsi"] if detail["rsi"] else "—")

    st.write(f"**Signal:** {detail['signal']}  (strength {detail['strength']:+.1f})")
    st.write(f"**1H Trend:** {detail['trend_1h']}  |  **4H Trend:** {detail['trend_4h']}")
    st.write(f"**MA:** {detail['ma_signal']}  |  **MACD:** {detail['macd_signal']}")
    st.write(f"**Reason:** {detail['summary']}")

    # Simple price chart
    df = get_ohlc(selected, "1h", 80)
    if df is not None and not df.empty:
        st.line_chart(df.set_index("openTime")["Close"], height=250)

# Footer
st.divider()
st.caption("Data: biquote (free MetaTrader 5 feed) • Not financial advice • For education only")
st.caption("Open this page on your phone browser for the best experience.")

# Auto refresh
if auto:
    time.sleep(60)
    st.rerun()

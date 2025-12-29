import streamlit as st
import requests
import time
from datetime import datetime
import pytz

# =========================
# CONFIG
# =========================
DELTA_BASE = "https://api.india.delta.exchange"
REFRESH_SECONDS = 300  # 5 minutes
IST = pytz.timezone("Asia/Kolkata")

st.set_page_config(
    page_title="BTC MOVE / CP Straddle Scanner",
    layout="wide"
)

st.title("📊 BTC MOVE / CP Straddle Scanner")
st.caption("MOVE preferred • CP fallback • Auto refresh every 5 minutes")

# Auto refresh (Streamlit-safe)
st.markdown(
    f"<meta http-equiv='refresh' content='{REFRESH_SECONDS}'>",
    unsafe_allow_html=True
)

# =========================
# HELPERS
# =========================
def get_btc_price():
    r = requests.get(f"{DELTA_BASE}/v2/tickers/BTCUSD", timeout=10)
    r.raise_for_status()
    return float(r.json()["result"]["mark_price"])


def get_options():
    r = requests.get(f"{DELTA_BASE}/v2/products", timeout=15)
    r.raise_for_status()
    return r.json()["result"]


def nearest_expiry(products):
    expiries = sorted(
        {p["expiry"] for p in products if p["expiry"] is not None}
    )
    return expiries[0] if expiries else None


def is_move(p):
    return "MOVE" in p["symbol"]


def build_straddles(products, expiry, btc):
    rows = []

    for p in products:
        if p["expiry"] != expiry:
            continue

        symbol = p["symbol"]

        if "BTC" not in symbol:
            continue

        strike = p.get("strike_price")
        if not strike:
            continue

        try:
            mark = float(p.get("mark_price", 0))
            oi = float(p.get("open_interest", 0))
            vol = float(p.get("volume_24h", 0))
        except:
            continue

        rows.append({
            "strike": int(strike),
            "type": "MOVE" if is_move(p) else "CP",
            "extrinsic": mark,
            "oi": oi,
            "volume": vol
        })

    return rows


def render_table(title, rows, best_strike):
    st.subheader(title)

    if not rows:
        st.info("No data available")
        return

    display = []
    for r in rows:
        display.append({
            "Strike": r["strike"],
            "Type": r["type"],
            "Extrinsic": round(r["extrinsic"], 2),
            "Volume($)": round(r["volume"], 2),
            "OI($)": round(r["oi"], 2),
            "⭐": "⭐" if r["strike"] == best_strike else ""
        })

    st.dataframe(display, use_container_width=True)


# =========================
# MAIN
# =========================
try:
    st.warning("Scanner warming up…")

    btc_price = get_btc_price()
    products = get_options()
    expiry = nearest_expiry(products)

    rows = build_straddles(products, expiry, btc_price)

    if not rows:
        st.error("No valid straddles found")
        st.stop()

    # Prefer MOVE
    move_rows = [r for r in rows if r["type"] == "MOVE"]
    use_rows = move_rows if move_rows else rows
    data_source = "MOVE options" if move_rows else "CP straddles"

    # Best strike = highest OI
    best = max(use_rows, key=lambda x: x["oi"])["strike"]

    ist_now = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")

    # HEADER
    st.markdown(f"""
**Expiry:** `{expiry}`  
**BTC Price:** `{btc_price:.2f}`  
**Data Source:** `{data_source}`  
**Last Updated (IST):** `{ist_now}`
""")

    col1, col2, col3 = st.columns(3)

    with col1:
        render_table(
            "TOP BY SCORE",
            sorted(use_rows, key=lambda x: (x["oi"], x["extrinsic"]), reverse=True)[:5],
            best
        )

    with col2:
        render_table(
            "TOP BY EXTRINSIC",
            sorted(use_rows, key=lambda x: x["extrinsic"], reverse=True)[:5],
            best
        )

    with col3:
        render_table(
            "TOP BY OI (BIG TRADER VIEW)",
            sorted(use_rows, key=lambda x: x["oi"], reverse=True)[:5],
            best
        )

except Exception as e:
    st.error("Live scan failed. Refresh page.")

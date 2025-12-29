import streamlit as st
import requests
from datetime import datetime
import pytz

# ================= CONFIG =================
DELTA = "https://api.india.delta.exchange"
REFRESH_SEC = 300
IST = pytz.timezone("Asia/Kolkata")

st.set_page_config(page_title="BTC MOVE / CP Straddle Scanner", layout="wide")
st.title("📊 BTC MOVE / CP Straddle Scanner")
st.caption("MOVE preferred • CP fallback • Auto refresh every 5 minutes")

# Auto refresh (safe)
st.markdown(f"<meta http-equiv='refresh' content='{REFRESH_SEC}'>", unsafe_allow_html=True)

# ================= HELPERS =================
def get_btc_price():
    r = requests.get(f"{DELTA}/v2/tickers?contract_types=perpetual_futures", timeout=15)
    r.raise_for_status()
    for t in r.json()["result"]:
        if t["symbol"] == "BTCUSD":
            return float(t["mark_price"])
    raise Exception("BTC price not found")


def get_products():
    r = requests.get(f"{DELTA}/v2/products", timeout=20)
    r.raise_for_status()
    return r.json()["result"]


def nearest_expiry(products):
    expiries = sorted({p["expiry"] for p in products if p["expiry"]})
    return expiries[0] if expiries else None


def is_move(symbol):
    return "MOVE" in symbol.upper()


def build_rows(products, expiry):
    rows = []
    for p in products:
        if p.get("expiry") != expiry:
            continue
        if "BTC" not in p["symbol"]:
            continue
        if not p.get("strike_price"):
            continue

        rows.append({
            "strike": int(p["strike_price"]),
            "type": "MOVE" if is_move(p["symbol"]) else "CP",
            "extrinsic": float(p.get("mark_price", 0)),
            "oi": float(p.get("open_interest", 0)),
            "volume": float(p.get("volume_24h", 0))
        })
    return rows


def render(title, rows, best):
    st.subheader(title)
    if not rows:
        st.info("No data")
        return

    table = []
    for r in rows:
        table.append({
            "Strike": r["strike"],
            "Type": r["type"],
            "Extrinsic": round(r["extrinsic"], 2),
            "Volume($)": round(r["volume"], 2),
            "OI($)": round(r["oi"], 2),
            "⭐": "⭐" if r["strike"] == best else ""
        })
    st.dataframe(table, use_container_width=True)


# ================= MAIN =================
try:
    st.warning("Scanner warming up…")

    btc = get_btc_price()
    products = get_products()
    expiry = nearest_expiry(products)

    rows = build_rows(products, expiry)
    if not rows:
        st.error("No BTC straddles found")
        st.stop()

    # MOVE preferred
    move_rows = [r for r in rows if r["type"] == "MOVE"]
    active = move_rows if move_rows else rows
    source = "MOVE options" if move_rows else "CP straddles"

    best = max(active, key=lambda x: x["oi"])["strike"]
    now = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")

    st.markdown(f"""
**Expiry:** `{expiry}`  
**BTC Price:** `{btc:.2f}`  
**Data Source:** `{source}`  
**Last Updated (IST):** `{now}`
""")

    c1, c2, c3 = st.columns(3)

    with c1:
        render("TOP BY SCORE", sorted(active, key=lambda x: (x["oi"], x["extrinsic"]), reverse=True)[:5], best)
    with c2:
        render("TOP BY EXTRINSIC", sorted(active, key=lambda x: x["extrinsic"], reverse=True)[:5], best)
    with c3:
        render("TOP BY OI (BIG TRADER VIEW)", sorted(active, key=lambda x: x["oi"], reverse=True)[:5], best)

except Exception as e:
    st.error("Live scan failed. Refresh page.")

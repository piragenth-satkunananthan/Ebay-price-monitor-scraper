"""
PriceWatch Pro — Ultra-Advanced eBay Price Intelligence Suite
=============================================================
Features:
  • AI Buy Advisor (Claude API)
  • Multi-model ML Forecasting (Linear, Polynomial, Exponential Smoothing)
  • Technical Indicators: RSI, Bollinger Bands, MACD, Price Velocity
  • OHLC Candlestick Charts
  • Calendar Price Heatmap
  • Product Correlation Matrix
  • Portfolio P&L Tracker (quantity + cost basis)
  • Anomaly / Outlier Detection
  • Discord & Slack Webhook Alerts
  • Side-by-side Product Comparison + Radar Chart
  • Auto-Refresh with Countdown
  • Per-product Tags & Notes
  • Smart Deal Score (multi-factor)
  • CSV Bulk Import / Export
  • Ticker tape live feed
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import requests
import time

import database as db
from product_search import scrape_search_page

# ── Optional deps ──
try:
    from scipy.optimize import curve_fit
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

try:
    import anthropic
    ANTHROPIC_OK = True
except ImportError:
    ANTHROPIC_OK = False

# ══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="PriceWatch Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════
#  CSS — Luxury Dark Terminal
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Outfit:wght@300;400;600;800&display=swap');

*, html, body { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
code, [data-testid="stMetricValue"] { font-family: 'Space Mono', monospace !important; }

:root {
  --bg0:#06080c; --bg1:#0b0f18; --bg2:#111827; --bg3:#1a2233;
  --border:#1f2d42; --text1:#e2e8f0; --text2:#8b9ab5;
  --accent:#38bdf8; --green:#34d399; --red:#f87171;
  --amber:#fbbf24; --purple:#a78bfa;
}

.stApp { background: var(--bg0); }
[data-testid="stSidebar"] { background: var(--bg1); border-right: 1px solid var(--border); }

.card {
  background: var(--bg1); border: 1px solid var(--border);
  border-radius: 14px; padding: 1.25rem 1.5rem; margin-bottom: 0.85rem;
  transition: border-color 0.25s, box-shadow 0.25s;
}
.card:hover { border-color: var(--accent); box-shadow: 0 0 20px rgba(56,189,248,0.07); }

.page-title {
  font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em;
  background: linear-gradient(100deg, var(--accent), var(--purple));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin-bottom: 0;
}
.page-sub { color: var(--text2); font-size: 0.88rem; margin-top: -4px; margin-bottom: 1.2rem; }

.badge {
  display: inline-block; padding: 2px 11px; border-radius: 20px;
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em;
  font-family: 'Space Mono', monospace;
}
.badge-hot   { background:rgba(248,113,113,.15); color:#f87171; border:1px solid rgba(248,113,113,.35); }
.badge-good  { background:rgba(52,211,153,.15);  color:#34d399; border:1px solid rgba(52,211,153,.35); }
.badge-fair  { background:rgba(251,191,36,.15);  color:#fbbf24; border:1px solid rgba(251,191,36,.35); }
.badge-watch { background:rgba(139,154,181,.12); color:#8b9ab5; border:1px solid rgba(139,154,181,.3); }
.badge-hit   { background:rgba(52,211,153,.2);   color:#34d399; border:1px solid #34d399; animation:blink 1.4s infinite; }
.badge-anom  { background:rgba(251,191,36,.2);   color:#fbbf24; border:1px solid #fbbf24; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.45} }

[data-testid="stMetric"] {
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.75rem 1rem;
}
hr { border-color: var(--border) !important; margin: 0.8rem 0 !important; }

.score-bar-wrap { background:var(--bg3); border-radius:6px; height:5px; margin:6px 0 3px; }
.score-bar { height:5px; border-radius:6px; transition:width .6s; }

.chip {
  display:inline-block; font-family:'Space Mono',monospace; font-size:0.68rem;
  background:var(--bg3); border:1px solid var(--border);
  border-radius:6px; padding:2px 8px; color:var(--text2); margin:2px 2px 0 0;
}
.chip-up   { color:var(--green);  border-color:rgba(52,211,153,.3); }
.chip-down { color:var(--red);    border-color:rgba(248,113,113,.3); }
.chip-blue { color:var(--accent); border-color:rgba(56,189,248,.3); }

.ai-box {
  background: linear-gradient(135deg,rgba(167,139,250,.08),rgba(56,189,248,.06));
  border: 1px solid rgba(167,139,250,.3); border-radius: 12px;
  padding: 1.2rem 1.4rem; font-size: .93rem; line-height: 1.7; color: var(--text1);
}

.ticker-wrap { overflow:hidden; background:var(--bg2); border-bottom:1px solid var(--border); padding:6px 0; margin-bottom:1rem; }
.ticker-inner { display:flex; gap:2.5rem; white-space:nowrap; animation:ticker 35s linear infinite; font-family:'Space Mono',monospace; font-size:.75rem; color:var(--text2); }
@keyframes ticker { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }

.countdown { font-family:'Space Mono',monospace; font-size:.8rem; background:var(--bg3); border:1px solid var(--border); border-radius:8px; padding:4px 12px; color:var(--accent); display:inline-block; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  CACHE HELPERS
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=600)
def fetch_products():
    return db.get_monitored_products()

@st.cache_data(ttl=600)
def fetch_history(pid):
    return db.get_product_price_history(pid)

def bust_cache():
    fetch_products.clear()
    fetch_history.clear()


# ══════════════════════════════════════════════════════════════
#  ANALYTICS ENGINE
# ══════════════════════════════════════════════════════════════

def price_stats(df):
    if df is None or df.empty:
        return {}
    p = df.sort_values("date")["price"].astype(float)
    vel = float(p.diff().mean()) if len(p) > 1 else 0.0
    return dict(
        current=float(p.iloc[-1]),
        prev=float(p.iloc[-2]) if len(p) > 1 else None,
        min=float(p.min()), max=float(p.max()),
        avg=float(p.mean()),
        std=float(p.std()) if len(p) > 1 else 0.0,
        drop_pct=round((p.max()-p.iloc[-1])/p.max()*100, 1) if p.max() > 0 else 0.0,
        velocity=round(vel, 3), n=len(p),
    )

def rsi(prices: pd.Series, period=14) -> pd.Series:
    d = prices.diff()
    g = d.clip(lower=0).rolling(period, min_periods=1).mean()
    l = (-d.clip(upper=0)).rolling(period, min_periods=1).mean()
    return 100 - (100 / (1 + g / (l + 1e-9)))

def bollinger(prices: pd.Series, window=10, ns=2):
    mid = prices.rolling(window, min_periods=1).mean()
    std = prices.rolling(window, min_periods=1).std().fillna(0)
    return mid, mid + ns*std, mid - ns*std

def macd(prices: pd.Series):
    e12 = prices.ewm(span=12, adjust=False).mean()
    e26 = prices.ewm(span=26, adjust=False).mean()
    m   = e12 - e26
    return m, m.ewm(span=9, adjust=False).mean()

def anomalies(df: pd.DataFrame, z=2.0):
    if df is None or len(df) < 4: return []
    p = df["price"].astype(float)
    return list(df[np.abs((p - p.mean()) / (p.std() + 1e-9)) > z].index)

def deal_score(df: pd.DataFrame):
    blank = {"score": None, "label": "⏳ WATCH", "css": "badge-watch", "drop_pct": 0, "below_avg": 0}
    if df is None or len(df) < 2: return blank
    p = df.sort_values("date")["price"].astype(float)
    cu = p.iloc[-1]; mx = p.max(); mn = p.min(); av = p.mean()
    drop  = (mx - cu) / mx * 100 if mx > 0 else 0
    ba    = max(0, (av - cu) / av * 100) if av > 0 else 0
    nm    = 1 - (cu - mn) / (mx - mn + 1e-9)
    slope = float(np.polyfit(range(len(p)), p.values, 1)[0]) if len(p) >= 3 else 0
    tot   = int(min(40, drop*1.4) + min(30, ba*1.5) + min(20, max(0, -slope*4)) + 10*nm)
    tot   = max(0, min(100, tot))
    if tot >= 75:   lb, css = "🔥 HOT",  "badge-hot"
    elif tot >= 50: lb, css = "✅ GOOD", "badge-good"
    elif tot >= 25: lb, css = "👁 FAIR", "badge-fair"
    else:           lb, css = "⏳ WATCH","badge-watch"
    return {"score": tot, "label": lb, "css": css, "drop_pct": round(drop,1), "below_avg": round(ba,1)}

def ohlc_weekly(df: pd.DataFrame):
    df = df.copy()
    df["date"]  = pd.to_datetime(df["date"])
    df["price"] = df["price"].astype(float)
    ohlc = df.set_index("date").sort_index()["price"].resample("W").ohlc().dropna()
    ohlc.index = ohlc.index.strftime("%Y-%m-%d")
    return ohlc.reset_index().rename(columns={"date":"week"})

def forecast_multi(df: pd.DataFrame, days: int):
    df = df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])
    p  = df["price"].astype(float).values
    t  = np.arange(len(p))
    ft = np.arange(len(p), len(p)+days)
    fd = [df["date"].max() + timedelta(days=i+1) for i in range(days)]
    out = {}
    out["Linear"]     = np.polyval(np.polyfit(t, p, 1), ft)
    out["Polynomial"] = np.polyval(np.polyfit(t, p, min(2,len(t)-1)), ft)
    lv, lt = p[0], (p[1]-p[0]) if len(p)>1 else 0
    for v in p[1:]:
        pl=lv; lv=0.4*v+(1-0.4)*(lv+lt); lt=0.2*(lv-pl)+(1-0.2)*lt
    out["Holt ETS"] = [lv+lt*(i+1) for i in range(days)]
    if SCIPY_OK and len(p) >= 4:
        try:
            def ef(x,a,b,c): return a*np.exp(b*x)+c
            popt,_ = curve_fit(ef, t, p, maxfev=3000, p0=[p[0],0.001,0])
            out["Exponential"] = ef(ft, *popt)
        except Exception:
            pass
    return fd, out

def webhook(url: str, payload: dict) -> bool:
    try:
        r = requests.post(url, json=payload, timeout=6)
        return r.status_code in (200, 204)
    except Exception:
        return False

def ticker_html(products, stats_list):
    items = []
    for p, s in zip(products, stats_list):
        if not s.get("current"): continue
        delta = (s["current"] - s["prev"]) if s.get("prev") else 0
        sign  = "▲" if delta >= 0 else "▼"
        col   = "var(--red)" if delta >= 0 else "var(--green)"
        name  = p["title"][:22]
        items.append(
            f'<span style="color:var(--text1)">{name}</span> '
            f'<span style="color:var(--accent);font-weight:700">${s["current"]:.2f}</span> '
            f'<span style="color:{col}">{sign}${abs(delta):.2f}</span>'
        )
    body = "  ·  ".join(items)
    return f'<div class="ticker-wrap"><div class="ticker-inner">{body}  ·  {body}</div></div>'


# ══════════════════════════════════════════════════════════════
#  SESSION INIT
# ══════════════════════════════════════════════════════════════
_defaults = dict(
    results_df=pd.DataFrame(), active_chart=None,
    target_prices={}, portfolio={}, tags={}, notes={},
    auto_refresh=False, refresh_interval=300, last_refresh=time.time(),
    compare_ids=[], webhook_discord="", webhook_slack="", anthropic_key="",
)
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<p style="font-size:1.35rem;font-weight:800;background:linear-gradient(90deg,#38bdf8,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent">📡 PriceWatch Pro</p>', unsafe_allow_html=True)
    st.caption("eBay Intelligence Suite · v3.0")
    st.divider()

    with st.expander("🔄 Auto-Refresh"):
        st.session_state.auto_refresh = st.toggle("Enable", value=st.session_state.auto_refresh)
        st.session_state.refresh_interval = st.select_slider(
            "Interval", [60,120,300,600,1800], value=st.session_state.refresh_interval,
            format_func=lambda x: f"{x//60}m")
        if st.session_state.auto_refresh:
            elapsed = int(time.time() - st.session_state.last_refresh)
            remaining = max(0, st.session_state.refresh_interval - elapsed)
            st.markdown(f'<span class="countdown">⏱ {remaining}s to refresh</span>', unsafe_allow_html=True)
            if elapsed >= st.session_state.refresh_interval:
                bust_cache(); st.session_state.last_refresh = time.time(); st.rerun()

    if st.button("🔄 Force Refresh", use_container_width=True):
        bust_cache(); st.toast("Cache cleared ✅")

    st.divider()

    with st.expander("🔮 Forecast"):
        forecast_days  = st.slider("Days ahead", 7, 90, 21, step=7)
        show_conf_band = st.toggle("Confidence band", True)

    with st.expander("🔔 Thresholds"):
        global_drop_pct = st.slider("Drop alert (%)", 1, 80, 10)
        rsi_os          = st.slider("RSI oversold",   10, 45, 30)

    with st.expander("🪝 Webhooks"):
        st.session_state.webhook_discord = st.text_input("Discord URL", value=st.session_state.webhook_discord, type="password")
        st.session_state.webhook_slack   = st.text_input("Slack URL",   value=st.session_state.webhook_slack,   type="password")
        if st.button("Test Discord"): st.success("OK") if webhook(st.session_state.webhook_discord,{"content":"Test ✅"}) else st.error("Failed")
        if st.button("Test Slack"):   st.success("OK") if webhook(st.session_state.webhook_slack,  {"text":"Test ✅"})    else st.error("Failed")

    with st.expander("🤖 Claude AI"):
        st.session_state.anthropic_key = st.text_input("Anthropic API Key", value=st.session_state.anthropic_key, type="password", placeholder="sk-ant-…")

    st.divider()
    st.caption(f"Now: {datetime.now().strftime('%H:%M:%S')}")


# ══════════════════════════════════════════════════════════════
#  PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════
def page_dashboard():
    st.markdown('<p class="page-title">Dashboard</p><p class="page-sub">Real-time portfolio overview & market intelligence</p>', unsafe_allow_html=True)

    pdf = fetch_products()
    if pdf.empty:
        st.info("No products tracked. Head to **Search** to get started."); return

    prods = pdf.to_dict("records")
    all_s = [price_stats(fetch_history(p["id"])) for p in prods]
    all_d = [deal_score(fetch_history(p["id"]))  for p in prods]

    st.markdown(ticker_html(prods, all_s), unsafe_allow_html=True)

    # KPIs
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Tracked", len(prods))
    c2.metric("🔥 Hot Deals",    sum(1 for d in all_d if d["score"] and d["score"]>=75))
    c3.metric("Avg Drop%",       f"{sum(s.get('drop_pct',0) for s in all_s)/max(1,len(all_s)):.1f}%")
    c4.metric("Total Savings",   f"${sum((s.get('max',0) or 0)-(s.get('current',0) or 0) for s in all_s):.2f}")
    port_val = sum((s.get('current',0) or 0) * st.session_state.portfolio.get(p['id'],{}).get('qty',0) for s,p in zip(all_s,prods))
    c5.metric("Portfolio Value", f"${port_val:.2f}")
    c6.metric("⚠️ Anomalies",    sum(1 for p in prods if len(anomalies(fetch_history(p["id"])))>0))

    st.divider()
    col_l, col_r = st.columns([3,2])
    with col_l:
        st.subheader("🏆 Leaderboard")
        rows = [{"Product":p["title"][:42],"Price":f"${s.get('current',0):.2f}",
                 "Drop%":f"{s.get('drop_pct',0):.1f}%","Score":d["score"] or 0,
                 "Tier":d["label"],"Vel":f"{s.get('velocity',0):+.3f}"}
                for p,s,d in zip(prods,all_s,all_d) if s]
        if rows:
            st.dataframe(pd.DataFrame(rows).sort_values("Score",ascending=False), use_container_width=True, hide_index=True)

    with col_r:
        st.subheader("Deal Distribution")
        tier_map={"⏳ WATCH":0,"👁 FAIR":0,"✅ GOOD":0,"🔥 HOT":0}
        for d in all_d:
            for k in tier_map:
                if k in d["label"]: tier_map[k]+=1; break
        fig = go.Figure(go.Pie(
            labels=list(tier_map.keys()), values=list(tier_map.values()), hole=0.55,
            marker=dict(colors=["#374151","#fbbf24","#34d399","#f87171"]),
            textinfo="label+value",
        ))
        fig.update_layout(template="plotly_dark", showlegend=False,
                          paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📈 All-Product Timeline")
    series = []
    for p in prods:
        h = fetch_history(p["id"])
        if h is not None and not h.empty:
            h2 = h.copy(); h2["product"]=p["title"][:32]; series.append(h2)
    if series:
        comb = pd.concat(series); comb["date"]=pd.to_datetime(comb["date"])
        fig2 = px.line(comb, x="date", y="price", color="product", template="plotly_dark",
                       labels={"price":"Price ($)","date":"Date"})
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           hovermode="x unified", legend=dict(orientation="h",y=-0.2),
                           height=380, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True)

    # Correlation matrix
    if len(prods) >= 2:
        st.subheader("🔗 Price Correlation Matrix")
        sd = {}
        for p in prods:
            h = fetch_history(p["id"])
            if h is not None and len(h) > 2:
                h2 = h.sort_values("date").copy()
                h2["date"]=pd.to_datetime(h2["date"]).dt.date
                h2=h2.drop_duplicates("date").set_index("date")["price"].astype(float)
                sd[p["title"][:18]]=h2
        if len(sd)>=2:
            corr=pd.DataFrame(sd).corr()
            fig3=px.imshow(corr, template="plotly_dark", color_continuous_scale="RdBu_r",
                           zmin=-1, zmax=1, aspect="auto")
            fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig3, use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  PAGE: SEARCH
# ══════════════════════════════════════════════════════════════
def page_search():
    st.markdown('<p class="page-title">Product Search</p><p class="page-sub">Scrape eBay and add to your watchlist</p>', unsafe_allow_html=True)
    st.divider()

    c1,c2 = st.columns([5,1], vertical_alignment="bottom")
    with c1: keyword = st.text_input("Keyword", placeholder="e.g.  RTX 5090  ·  iPhone 16 Pro  ·  Leica M11", label_visibility="collapsed")
    with c2: go_btn  = st.button("🔍 Search", use_container_width=True, type="primary")

    with st.expander("📥 Bulk CSV Import"):
        st.caption("Required columns: `title`, `link`, `image_link`")
        uploaded = st.file_uploader("Upload CSV", type="csv", label_visibility="collapsed")
        if uploaded and st.button("Import"):
            try:
                imp=pd.read_csv(uploaded)
                miss={"title","link","image_link"}-set(imp.columns)
                if miss: st.error(f"Missing: {miss}")
                else:
                    n=sum(db.add_new_product(r.title,r.link,r.image_link) for r in imp.itertuples())
                    st.success(f"Imported {n} ✅"); bust_cache()
            except Exception as e: st.error(str(e))

    if go_btn and keyword:
        with st.spinner(f"Scraping eBay for **{keyword}** …"):
            res=scrape_search_page(keyword)
        if not res: st.warning("No results.")
        else:
            df=pd.DataFrame(res)
            if "select" not in df.columns: df.insert(0,"select",False)
            st.session_state.results_df=df

    rdf=st.session_state.results_df
    if not rdf.empty:
        st.divider()
        fa,fb=st.columns([3,2])
        with fa: ft=st.text_input("Filter",placeholder="Narrow results…")
        with fb: st.selectbox("Sort",["Default","Price ↑","Price ↓"])
        disp=rdf[rdf["title"].str.contains(ft,case=False,na=False)] if ft else rdf.copy()
        edited=st.data_editor(disp,use_container_width=True,hide_index=True,column_config={
            "select":     st.column_config.CheckboxColumn("Track",width="small"),
            "image_link": st.column_config.ImageColumn("Image",width="small"),
            "title":      st.column_config.TextColumn("Title",width="large"),
            "price_range":st.column_config.TextColumn("Price"),
            "link":       st.column_config.LinkColumn("Listing",display_text="eBay →"),
        })
        sel=edited[edited["select"]==True]
        st.caption(f"{len(sel)} selected · {len(disp)} shown")
        b1,b2=st.columns(2)
        with b1:
            if st.button("➕ Add to Watchlist",type="primary",use_container_width=True):
                if sel.empty: st.warning("Select at least one.")
                else:
                    n=sum(db.add_new_product(r["title"],r["link"],r["image_link"]) for _,r in sel.iterrows())
                    st.toast(f"✅ Added {n}"); bust_cache()
        with b2:
            csv=disp.drop(columns=["select"],errors="ignore").to_csv(index=False)
            st.download_button("📤 Export Results",csv,"results.csv","text/csv",use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  PAGE: ANALYTICS
# ══════════════════════════════════════════════════════════════
def page_analytics():
    st.markdown('<p class="page-title">Price Analytics</p><p class="page-sub">Technical indicators · Forecasts · Deal scoring · Anomaly detection</p>', unsafe_allow_html=True)
    st.divider()

    pdf=fetch_products()
    if pdf.empty: st.info("Add products via Search first."); return

    with st.expander("🔽 Filter & Sort"):
        fc1,fc2,fc3,fc4=st.columns(4)
        with fc1: ft_name=st.text_input("Name")
        with fc2: ft_deal=st.multiselect("Tier",["🔥 HOT","✅ GOOD","👁 FAIR","⏳ WATCH"])
        with fc3: ft_sort=st.selectbox("Sort",["Default","Score↓","Price↑","Price↓","Drop%↓"])
        with fc4: ft_tag=st.text_input("Tag filter")

    b1,b2=st.columns(2)
    with b1:
        if st.button("📤 Export Watchlist"):
            rows=[{"title":p["title"],"link":p["link"],**price_stats(fetch_history(p["id"])),
                   **deal_score(fetch_history(p["id"]))} for _,p in pdf.iterrows()]
            st.download_button("⬇️ Download",pd.DataFrame(rows).to_csv(index=False),"watchlist.csv","text/csv")
    with b2:
        if st.button("🚀 Fire Active Webhooks"):
            n=0
            for _,p in pdf.iterrows():
                s=price_stats(fetch_history(p["id"])); d=deal_score(fetch_history(p["id"]))
                if d["score"] and d["score"]>=75 and s.get("current"):
                    msg=f"🔥 HOT DEAL — {p['title'][:60]} | ${s['current']:.2f} (-{s['drop_pct']}%)"
                    if st.session_state.webhook_discord: webhook(st.session_state.webhook_discord,{"content":msg}); n+=1
                    if st.session_state.webhook_slack:   webhook(st.session_state.webhook_slack,  {"text":msg});    n+=1
            st.toast(f"Fired {n} webhooks 🚀")

    st.divider()

    enriched=[]
    for _,p in pdf.iterrows():
        h=fetch_history(p["id"]); s=price_stats(h); d=deal_score(h)
        enriched.append((p,h,s,d))

    if ft_name: enriched=[(p,h,s,d) for p,h,s,d in enriched if ft_name.lower() in p["title"].lower()]
    if ft_deal:  enriched=[(p,h,s,d) for p,h,s,d in enriched if any(t in d["label"] for t in ft_deal)]
    if ft_tag:
        want=[t.strip().lower() for t in ft_tag.split(",")]
        enriched=[(p,h,s,d) for p,h,s,d in enriched if any(w in [x.lower() for x in st.session_state.tags.get(p["id"],[])] for w in want)]
    sm={"Score↓":lambda x:-(x[3]["score"] or 0),"Price↑":lambda x:x[2].get("current") or 1e9,
        "Price↓":lambda x:-(x[2].get("current") or 0),"Drop%↓":lambda x:-(x[2].get("drop_pct") or 0)}
    if ft_sort in sm: enriched.sort(key=sm[ft_sort])

    for product,history_df,stats,ds in enriched:
        pid=product["id"]
        anom_idx=anomalies(history_df)
        rsi_val=None
        if history_df is not None and len(history_df)>=5:
            rsi_val=round(float(rsi(history_df.sort_values("date")["price"].astype(float)).iloc[-1]),1)

        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            ic,infc,mc,ac=st.columns([1,2.8,2.2,1.1],vertical_alignment="center")

            with ic:
                st.image(product.get("image_link",""),use_container_width=True)

            with infc:
                bdgs=f'<span class="badge {ds["css"]}">{ds["label"]} {ds["score"] or "?"}/100</span>'
                if anom_idx: bdgs+=' <span class="badge badge-anom">⚠️ ANOMALY</span>'
                if rsi_val and rsi_val<rsi_os: bdgs+=f' <span class="badge badge-good">RSI {rsi_val} OVERSOLD</span>'
                st.markdown(f"### {product['title'][:58]}")
                st.markdown(bdgs,unsafe_allow_html=True)
                st.caption(f"[eBay ↗]({product['link']})")

                tags=st.text_input("🏷",value=",".join(st.session_state.tags.get(pid,[])),key=f"tag_{pid}",label_visibility="collapsed",placeholder="Tags…")
                note=st.text_input("📝",value=st.session_state.notes.get(pid,""),key=f"note_{pid}",label_visibility="collapsed",placeholder="Note…")
                st.session_state.tags[pid]=[t.strip() for t in tags.split(",") if t.strip()]
                st.session_state.notes[pid]=note

                if stats:
                    vel=stats.get("velocity",0); vd="up" if vel>=0 else "down"
                    bar_col={"badge-hot":"#f87171","badge-good":"#34d399","badge-fair":"#fbbf24","badge-watch":"#6b7280"}.get(ds["css"],"#6b7280")
                    st.markdown(f"""
                      <div style="margin-top:6px">
                        <span class="chip chip-{vd}">{"▲" if vel>=0 else "▼"}${abs(vel):.3f}/day</span>
                        <span class="chip">Drop {ds['drop_pct']}%</span>
                        <span class="chip">Avg gap {ds['below_avg']}%</span>
                        {"<span class='chip chip-blue'>RSI "+str(rsi_val)+"</span>" if rsi_val else ""}
                      </div>
                      <div class="score-bar-wrap"><div class="score-bar" style="width:{ds['score'] or 0}%;background:{bar_col}"></div></div>
                    """,unsafe_allow_html=True)

            with mc:
                if stats:
                    ra,rb=st.columns(2)
                    with ra:
                        if stats.get("prev"):
                            st.metric("Current",f"${stats['current']:.2f}",f"${stats['current']-stats['prev']:.2f}",delta_color="inverse")
                        else:
                            st.metric("Current",f"${stats['current']:.2f}")
                        st.metric("Avg",f"${stats['avg']:.2f}")
                    with rb:
                        st.metric("Min/Max",f"${stats['min']:.2f}",f"↑${stats['max']:.2f}",delta_color="off")
                        st.metric("σ",f"${stats['std']:.2f}")

                    port=st.session_state.portfolio.get(pid,{"qty":0,"cost_basis":0.0})
                    qa,qb=st.columns(2)
                    with qa: qty=st.number_input("Qty",0,999,port["qty"],key=f"qty_{pid}")
                    with qb: cost=st.number_input("Cost($)",0.0,99999.0,float(port["cost_basis"]),step=1.0,key=f"cost_{pid}")
                    st.session_state.portfolio[pid]={"qty":qty,"cost_basis":cost}
                    if qty>0:
                        cv=stats["current"]*qty; pnl=cv-cost
                        pnl_col="var(--green)" if pnl>=0 else "var(--red)"
                        st.markdown(f'<span class="chip">Portfolio ${cv:.2f} | <span style="color:{pnl_col}">P&L ${pnl:+.2f} ({pnl/cost*100 if cost else 0:+.1f}%)</span></span>',unsafe_allow_html=True)
                else:
                    st.metric("Current","Pending…",delta_color="off")

                tgt=st.session_state.target_prices.get(pid,0.0)
                new_tgt=st.number_input("🎯 Target($)",0.0,99999.0,float(tgt),step=0.5,key=f"tgt_{pid}")
                st.session_state.target_prices[pid]=new_tgt if new_tgt>0 else None
                if new_tgt and stats.get("current") and stats["current"]<=new_tgt:
                    st.markdown('<span class="badge badge-hit">🎯 TARGET HIT</span>',unsafe_allow_html=True)

            with ac:
                if st.button("📊 Chart",key=f"ch_{pid}",use_container_width=True):
                    st.session_state.active_chart=pid if st.session_state.active_chart!=pid else None
                if st.button("🤖 AI",key=f"ai_{pid}",use_container_width=True):
                    st.session_state[f"ai_{pid}"]=not st.session_state.get(f"ai_{pid}",False)
                if st.button("🆚 Compare",key=f"cmp_{pid}",use_container_width=True):
                    if pid not in st.session_state.compare_ids:
                        st.session_state.compare_ids.append(pid)
                        st.toast(f"Added ({len(st.session_state.compare_ids)}/4)")
                if st.button("🗑 Remove",key=f"del_{pid}",use_container_width=True):
                    db.delete_product(pid); bust_cache(); st.rerun()

            st.markdown("</div>",unsafe_allow_html=True)

        # AI Panel
        if st.session_state.get(f"ai_{pid}",False):
            key=st.session_state.anthropic_key
            if not key: st.warning("Add Anthropic API key in sidebar.")
            elif history_df is None or len(history_df)<3: st.warning("Not enough data for AI analysis.")
            else:
                with st.spinner("🤖 Claude is analyzing…"):
                    try:
                        hcsv=history_df.sort_values("date").tail(30).to_csv(index=False)
                        prompt=f"""You are an eBay price analyst. Price history CSV:
{hcsv}

Current: ${stats.get('current','?')}  Min: ${stats.get('min','?')}  Max: ${stats.get('max','?')}  Avg: ${stats.get('avg','?')}
Deal score: {ds['score']}/100 ({ds['label']})  Drop from peak: {ds['drop_pct']}%  RSI: {rsi_val or 'N/A'}
Product: {product['title']}

Respond in this exact format:
**Verdict**: BUY NOW / WAIT / HOLD OFF — one sentence reason
**Trend**: 2 sentences on price direction
**Risk**: 1 sentence on volatility/risk
**Suggested buy price**: if not buying now"""
                        client=anthropic.Anthropic(api_key=key)
                        msg=client.messages.create(model="claude-opus-4-5",max_tokens=420,
                                                   messages=[{"role":"user","content":prompt}])
                        txt=msg.content[0].text
                        st.markdown(f'<div class="ai-box">{txt.replace(chr(10),"<br>")}</div>',unsafe_allow_html=True)
                    except Exception as e: st.error(f"AI error: {e}")

        # Chart panel
        if st.session_state.active_chart==pid:
            if history_df is None or len(history_df)<2:
                st.warning("Not enough data."); st.divider(); continue

            hdf=history_df.sort_values("date").copy()
            hdf["date"]=pd.to_datetime(hdf["date"])
            hdf["price"]=hdf["price"].astype(float)

            t1,t2,t3,t4,t5,t6=st.tabs(["📈 Technical","🕯 Candlestick","🔮 Forecast","📅 Heatmap","📊 Stats","🗂 Raw"])

            with t1:
                sma5=hdf["price"].rolling(5,min_periods=1).mean()
                sma14=hdf["price"].rolling(14,min_periods=1).mean()
                ema9=hdf["price"].ewm(span=9,adjust=False).mean()
                bb_m,bb_u,bb_l=bollinger(hdf["price"])
                rsi_s=rsi(hdf["price"])
                mc_l,sg_l=macd(hdf["price"])
                anom_rows=hdf.iloc[anom_idx] if anom_idx else pd.DataFrame()

                fig=make_subplots(rows=3,cols=1,shared_xaxes=True,row_heights=[0.55,0.25,0.2],vertical_spacing=0.04,
                                  subplot_titles=["Price + Bollinger Bands","RSI","MACD"])
                fig.add_trace(go.Scatter(x=hdf["date"],y=hdf["price"],name="Price",line=dict(color="#38bdf8",width=2)),row=1,col=1)
                fig.add_trace(go.Scatter(x=hdf["date"],y=sma5,name="SMA5",line=dict(color="#34d399",width=1,dash="dot")),row=1,col=1)
                fig.add_trace(go.Scatter(x=hdf["date"],y=sma14,name="SMA14",line=dict(color="#a78bfa",width=1,dash="dot")),row=1,col=1)
                fig.add_trace(go.Scatter(x=hdf["date"],y=ema9,name="EMA9",line=dict(color="#fbbf24",width=1,dash="dash")),row=1,col=1)
                fig.add_trace(go.Scatter(x=hdf["date"],y=bb_u,name="BB Upper",line=dict(color="rgba(248,113,113,.5)",width=1)),row=1,col=1)
                fig.add_trace(go.Scatter(x=hdf["date"],y=bb_l,name="BB Lower",fill="tonexty",
                                         fillcolor="rgba(248,113,113,.05)",line=dict(color="rgba(248,113,113,.5)",width=1)),row=1,col=1)
                if not anom_rows.empty:
                    fig.add_trace(go.Scatter(x=anom_rows["date"],y=anom_rows["price"],mode="markers",
                                             name="Anomaly",marker=dict(color="#fbbf24",size=10,symbol="star")),row=1,col=1)
                tp=st.session_state.target_prices.get(pid)
                if tp: fig.add_hline(y=tp,line_dash="dot",line_color="#34d399",annotation_text=f"Target ${tp:.2f}",row=1,col=1)

                fig.add_trace(go.Scatter(x=hdf["date"],y=rsi_s,name="RSI",line=dict(color="#f59e0b",width=1.5)),row=2,col=1)
                fig.add_hline(y=rsi_os,line_dash="dot",line_color="#34d399",row=2,col=1)
                fig.add_hline(y=70,line_dash="dot",line_color="#f87171",row=2,col=1)

                fig.add_trace(go.Scatter(x=hdf["date"],y=mc_l,name="MACD",line=dict(color="#38bdf8",width=1.5)),row=3,col=1)
                fig.add_trace(go.Scatter(x=hdf["date"],y=sg_l,name="Signal",line=dict(color="#f87171",width=1,dash="dash")),row=3,col=1)
                hist_vals=mc_l-sg_l
                fig.add_trace(go.Bar(x=hdf["date"],y=hist_vals,name="Histogram",
                                     marker_color=["#34d399" if v>=0 else "#f87171" for v in hist_vals]),row=3,col=1)
                fig.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                                  hovermode="x unified",height=620,legend=dict(orientation="h",y=1.05),
                                  margin=dict(l=0,r=0,t=40,b=0))
                st.plotly_chart(fig,use_container_width=True)

            with t2:
                ohlc=ohlc_weekly(history_df)
                if len(ohlc)<2: st.info("Need 2+ weeks of data.")
                else:
                    fc=go.Figure(go.Candlestick(x=ohlc["week"],open=ohlc["open"],high=ohlc["high"],
                                                low=ohlc["low"],close=ohlc["close"],
                                                increasing_line_color="#34d399",decreasing_line_color="#f87171"))
                    fc.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                                     title="Weekly OHLC",xaxis_rangeslider_visible=False,height=400,
                                     margin=dict(l=0,r=0,t=40,b=0))
                    st.plotly_chart(fc,use_container_width=True)

            with t3:
                fd,models=forecast_multi(history_df,forecast_days)
                ff=go.Figure()
                ff.add_trace(go.Scatter(x=hdf["date"],y=hdf["price"],name="Historical",line=dict(color="#38bdf8",width=2)))
                cols_m={"Linear":"#fbbf24","Polynomial":"#a78bfa","Holt ETS":"#34d399","Exponential":"#f87171"}
                for mn,preds in models.items():
                    c=cols_m.get(mn,"#8b9ab5")
                    ff.add_trace(go.Scatter(x=fd,y=preds,name=mn,line=dict(color=c,width=1.8,dash="dash"),
                                            marker=dict(symbol="diamond",size=4)))
                    if show_conf_band and stats.get("std"):
                        std=stats["std"]
                        ff.add_trace(go.Scatter(
                            x=list(fd)+list(fd)[::-1],
                            y=list(np.array(preds)+std)+list(np.array(preds)-std)[::-1],
                            fill="toself",fillcolor=f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.08)" if len(c)==7 else "rgba(255,255,255,0.05)",
                            line=dict(color="rgba(0,0,0,0)"),showlegend=False
                        ))
                ff.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                                 hovermode="x unified",title=f"{forecast_days}-Day Multi-Model Forecast",
                                 xaxis_title="Date",yaxis_title="Price ($)",
                                 legend=dict(orientation="h",y=-0.25),height=450,margin=dict(l=0,r=0,t=40,b=0))
                st.plotly_chart(ff,use_container_width=True)
                curr=stats.get("current",0)
                cmp=[{"Model":m,"End Price":f"${float(v[-1]):.2f}","Δ":f"${float(v[-1])-curr:+.2f}",
                      "Dir":"📈 UP" if float(v[-1])>=curr else "📉 DOWN"} for m,v in models.items()]
                st.dataframe(pd.DataFrame(cmp),use_container_width=True,hide_index=True)

            with t4:
                cal=history_df.copy()
                cal["date"]=pd.to_datetime(cal["date"]); cal["price"]=cal["price"].astype(float)
                cal["week"]=cal["date"].dt.isocalendar().week.astype(int)
                cal["dow"]=cal["date"].dt.dayofweek
                if not cal.empty:
                    fh=px.density_heatmap(cal,x="dow",y="week",z="price",
                                          color_continuous_scale="RdYlGn_r",template="plotly_dark",
                                          title="Price by Day-of-Week × Week",
                                          labels={"dow":"Day (0=Mon)","week":"ISO Week","price":"Price ($)"})
                    fh.update_layout(paper_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=40,b=0))
                    st.plotly_chart(fh,use_container_width=True)
                    fv=go.Figure()
                    fv.add_trace(go.Violin(y=hdf["price"],box_visible=True,line_color="#38bdf8",
                                           meanline_visible=True,fillcolor="rgba(56,189,248,.15)",name="Price"))
                    fv.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",
                                     title="Price Distribution",height=300,margin=dict(l=0,r=0,t=40,b=0))
                    st.plotly_chart(fv,use_container_width=True)

            with t5:
                if stats:
                    sc=st.columns(4)
                    sc[0].metric("Current",f"${stats['current']:.2f}")
                    sc[1].metric("Min",f"${stats['min']:.2f}")
                    sc[2].metric("Max",f"${stats['max']:.2f}")
                    sc[3].metric("Avg",f"${stats['avg']:.2f}")
                    sc2=st.columns(4)
                    sc2[0].metric("Std Dev",f"${stats['std']:.2f}")
                    sc2[1].metric("Peak Drop",f"{stats['drop_pct']}%")
                    sc2[2].metric("Velocity",f"${stats['velocity']:+.3f}/day")
                    sc2[3].metric("RSI",str(rsi_val) if rsi_val else "N/A")
                    pct_at_or_below=(hdf["price"]<=stats["current"]).mean()*100
                    st.markdown(f'<span class="chip">Price was at or below current level **{pct_at_or_below:.1f}%** of recorded time</span>',unsafe_allow_html=True)
                    if anom_idx: st.warning(f"⚠️ {len(anom_idx)} anomalous price point(s) detected (>2σ). May be flash deals or scraper errors.")

            with t6:
                raw=hdf.sort_values("date",ascending=False).copy()
                raw["price"]=raw["price"].map("${:.2f}".format)
                st.dataframe(raw,use_container_width=True,hide_index=True)
                st.download_button("⬇️ Download CSV",history_df.to_csv(index=False),f"history_{pid}.csv","text/csv")

        st.divider()


# ══════════════════════════════════════════════════════════════
#  PAGE: COMPARE
# ══════════════════════════════════════════════════════════════
def page_compare():
    st.markdown('<p class="page-title">Compare</p><p class="page-sub">Side-by-side price analysis + radar chart</p>',unsafe_allow_html=True)
    st.divider()
    pdf=fetch_products()
    if pdf.empty: st.info("No products tracked."); return

    titles={row["id"]:row["title"][:50] for _,row in pdf.iterrows()}
    sel_ids=st.multiselect("Select up to 4 products",list(titles.keys()),
                           default=st.session_state.compare_ids[:4],
                           format_func=lambda x:titles.get(x,"?"),max_selections=4)
    st.session_state.compare_ids=sel_ids
    if len(sel_ids)<2: st.info("Select at least 2."); return

    COLS=["#38bdf8","#34d399","#fbbf24","#a78bfa"]
    cmp_rows=[]; fig_norm=go.Figure()
    for idx,pid in enumerate(sel_ids):
        row=pdf[pdf["id"]==pid].iloc[0]
        h=fetch_history(pid); s=price_stats(h); d=deal_score(h)
        rv=None
        if h is not None and len(h)>=5:
            rv=round(float(rsi(h.sort_values("date")["price"].astype(float)).iloc[-1]),1)
        cmp_rows.append({"Product":row["title"][:38],
                         "Current":f"${s.get('current',0):.2f}" if s else "—",
                         "Min":f"${s.get('min',0):.2f}" if s else "—",
                         "Max":f"${s.get('max',0):.2f}" if s else "—",
                         "Drop%":f"{s.get('drop_pct',0):.1f}%" if s else "—",
                         "σ":f"${s.get('std',0):.2f}" if s else "—",
                         "RSI":str(rv) if rv else "—",
                         "Score":d["score"] or "—","Tier":d["label"]})
        if h is not None and not h.empty:
            hdf=h.sort_values("date").copy()
            hdf["date"]=pd.to_datetime(hdf["date"]); hdf["price"]=hdf["price"].astype(float)
            base=hdf["price"].iloc[0]; hdf["pct"]=(hdf["price"]-base)/base*100
            fig_norm.add_trace(go.Scatter(x=hdf["date"],y=hdf["pct"],name=row["title"][:24],
                                          line=dict(color=COLS[idx],width=2),mode="lines+markers"))

    st.dataframe(pd.DataFrame(cmp_rows),use_container_width=True,hide_index=True)
    st.divider()

    fig_norm.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                           title="Normalised Price Change (% from first point)",xaxis_title="Date",yaxis_title="% Change",
                           hovermode="x unified",legend=dict(orientation="h",y=-0.25),height=400,margin=dict(l=0,r=0,t=40,b=0))
    st.plotly_chart(fig_norm,use_container_width=True)

    cats=["Deal Score","Drop%","Low Volatility","RSI Opp","History Depth"]
    fig_r=go.Figure()
    def sn(v,scale=1):
        try: return float(str(v).replace("$","").replace("%","").replace("—","0"))*scale
        except: return 0
    for idx,row in enumerate(cmp_rows):
        vals=[sn(row["Score"]),sn(row["Drop%"]),max(0,100-sn(row["σ"])*5),
              max(0,100-sn(row["RSI"])),min(100,sn(str(all_s[0].get("n",0) if False else 10))*5)]
        c=COLS[idx]
        rgb=f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.12)"
        fig_r.add_trace(go.Scatterpolar(r=vals+[vals[0]],theta=cats+[cats[0]],fill="toself",
                                         fillcolor=rgb,line=dict(color=c),name=row["Product"][:20]))
    fig_r.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",
                        polar=dict(bgcolor="rgba(0,0,0,0)"),title="Multi-dimension Radar",
                        legend=dict(orientation="h",y=-0.1),height=450,margin=dict(l=0,r=0,t=40,b=0))
    st.plotly_chart(fig_r,use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  PAGE: PORTFOLIO
# ══════════════════════════════════════════════════════════════
def page_portfolio():
    st.markdown('<p class="page-title">Portfolio</p><p class="page-sub">P&L tracker · allocation · unrealised gains</p>',unsafe_allow_html=True)
    st.divider()
    pdf=fetch_products()
    if pdf.empty: st.info("No products tracked."); return

    rows=[]; tc=tk=tp=0
    for _,p in pdf.iterrows():
        pid=p["id"]; h=fetch_history(pid); s=price_stats(h)
        port=st.session_state.portfolio.get(pid,{"qty":0,"cost_basis":0.0})
        qty=port["qty"]; cost=port["cost_basis"]
        if qty==0 or not s.get("current"): continue
        cv=s["current"]*qty; pnl=cv-cost; pct=pnl/cost*100 if cost>0 else 0
        tc+=cv; tk+=cost; tp+=pnl
        rows.append({"Product":p["title"][:38],"Qty":qty,"Cost":f"${cost:.2f}",
                     "Value":f"${cv:.2f}","P&L($)":f"${pnl:+.2f}","P&L(%)":f"{pct:+.1f}%",
                     "Status":"📈" if pnl>=0 else "📉","_val":cv})

    if not rows:
        st.info("Set quantities and cost basis in **Analytics** to populate portfolio."); return

    k1,k2,k3,k4=st.columns(4)
    k1.metric("Total Value",f"${tc:.2f}"); k2.metric("Total Cost",f"${tk:.2f}")
    k3.metric("Total P&L",f"${tp:+.2f}",delta_color="normal")
    k4.metric("P&L %",f"{(tp/tk*100 if tk else 0):+.1f}%")
    st.divider()
    disp=[{k:v for k,v in r.items() if k!="_val"} for r in rows]
    st.dataframe(pd.DataFrame(disp),use_container_width=True,hide_index=True)
    st.download_button("📤 Export",pd.DataFrame(disp).to_csv(index=False),"portfolio.csv","text/csv")
    st.divider()
    fig=px.pie(names=[r["Product"] for r in rows],values=[r["_val"] for r in rows],
               template="plotly_dark",title="Portfolio Allocation",hole=0.45)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=40,b=0))
    st.plotly_chart(fig,use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  PAGE: ALERTS
# ══════════════════════════════════════════════════════════════
def page_alerts():
    st.markdown('<p class="page-title">Alerts</p><p class="page-sub">Price targets · drop alerts · anomalies · webhooks</p>',unsafe_allow_html=True)
    st.divider()
    pdf=fetch_products()
    if pdf.empty: st.info("No products tracked."); return

    alerts=[]
    for _,p in pdf.iterrows():
        pid=p["id"]; h=fetch_history(pid); s=price_stats(h); d=deal_score(h)
        tgt=st.session_state.target_prices.get(pid)
        if not s.get("current"): continue
        if s["drop_pct"]>=global_drop_pct:
            alerts.append({"Product":p["title"][:43],"Type":f"🔻 Drop ≥{global_drop_pct}%",
                           "Price":f"${s['current']:.2f}","Detail":f"-{s['drop_pct']}% from peak","Link":p["link"]})
        if tgt and s["current"]<=tgt:
            alerts.append({"Product":p["title"][:43],"Type":"🎯 Target Hit",
                           "Price":f"${s['current']:.2f}","Detail":f"Target ${tgt:.2f}","Link":p["link"]})
        if d["score"] and d["score"]>=75:
            alerts.append({"Product":p["title"][:43],"Type":"🔥 Hot Deal",
                           "Price":f"${s['current']:.2f}","Detail":f"Score {d['score']}/100","Link":p["link"]})
        an=anomalies(h)
        if an:
            alerts.append({"Product":p["title"][:43],"Type":"⚠️ Anomaly",
                           "Price":f"${s['current']:.2f}","Detail":f"{len(an)} outlier(s)","Link":p["link"]})

    if alerts:
        st.error(f"🚨 {len(alerts)} alert(s) active")
        adf=pd.DataFrame(alerts)
        st.dataframe(adf.drop(columns=["Link"]),use_container_width=True,hide_index=True)
        if st.button("🚀 Fire All Webhooks",type="primary"):
            n=0
            for a in alerts:
                msg=f"{a['Type']} — {a['Product']} | {a['Price']} | {a['Detail']}"
                if st.session_state.webhook_discord: webhook(st.session_state.webhook_discord,{"content":msg}); n+=1
                if st.session_state.webhook_slack:   webhook(st.session_state.webhook_slack,{"text":msg}); n+=1
            st.toast(f"Fired {n} webhooks 🚀")
        st.download_button("📤 Export",adf.to_csv(index=False),"alerts.csv","text/csv")
    else:
        st.success(f"✅ No alerts. Watching: drops ≥{global_drop_pct}%, target prices, hot deals, anomalies.")


# ══════════════════════════════════════════════════════════════
#  NAVIGATION
# ══════════════════════════════════════════════════════════════
pg=st.navigation([
    st.Page(page_dashboard, title="Dashboard",  icon="🏠"),
    st.Page(page_search,    title="Search",     icon="🔍"),
    st.Page(page_analytics, title="Analytics",  icon="📊"),
    st.Page(page_compare,   title="Compare",    icon="🆚"),
    st.Page(page_portfolio, title="Portfolio",  icon="💼"),
    st.Page(page_alerts,    title="Alerts",     icon="🔔"),
])
pg.run()
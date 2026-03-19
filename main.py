import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import database as db
from product_search import scrape_search_page
import io

# ─────────────────────────────────────────────
#  Page Configuration
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="PriceWatch Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  Custom CSS — Dark Trading-Terminal Theme
# ─────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;700;800&display=swap');

  html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
  }
  code, .stCode, [data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
  }

  /* Background */
  .stApp { background: #090d13; }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: #0d1117;
    border-right: 1px solid #1e2733;
  }

  /* Cards */
  .pw-card {
    background: #0d1117;
    border: 1px solid #1e2733;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s;
  }
  .pw-card:hover { border-color: #3b82f6; }

  /* Deal Score Badge */
  .deal-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
  }
  .deal-hot   { background: #ff4b4b22; color: #ff4b4b; border: 1px solid #ff4b4b55; }
  .deal-good  { background: #f59e0b22; color: #f59e0b; border: 1px solid #f59e0b55; }
  .deal-fair  { background: #3b82f622; color: #3b82f6; border: 1px solid #3b82f655; }
  .deal-watch { background: #6b728022; color: #9ca3af; border: 1px solid #6b728055; }

  /* Target hit badge */
  .target-hit {
    background: #22c55e22; color: #22c55e;
    border: 1px solid #22c55e55;
    border-radius: 20px; padding: 2px 10px;
    font-size: 0.75rem; font-weight: 700;
    animation: pulse 1.5s infinite;
  }
  @keyframes pulse {
    0%,100% { opacity: 1; } 50% { opacity: 0.5; }
  }

  /* Metric overrides */
  [data-testid="stMetric"] {
    background: #0d1117;
    border: 1px solid #1e2733;
    border-radius: 10px;
    padding: 0.8rem 1rem;
  }

  /* Dividers */
  hr { border-color: #1e2733 !important; }

  /* Header accent */
  .pw-title {
    font-size: 2rem; font-weight: 800;
    background: linear-gradient(90deg, #3b82f6, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .pw-subtitle { color: #6b7280; font-size: 0.9rem; margin-top: -0.5rem; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Caching & Helpers
# ─────────────────────────────────────────────
@st.cache_data(ttl=600)
def fetch_monitored_products():
    return db.get_monitored_products()

@st.cache_data(ttl=600)
def fetch_price_history(product_id):
    return db.get_product_price_history(product_id)

def refresh_data():
    fetch_monitored_products.clear()
    fetch_price_history.clear()

def compute_deal_score(history_df: pd.DataFrame) -> dict:
    """Score a product 0–100. Returns dict with score + breakdown."""
    if history_df is None or len(history_df) < 2:
        return {"score": None, "label": "Insufficient Data", "css": "deal-watch"}

    prices = history_df.sort_values("date")["price"].astype(float)
    current   = prices.iloc[-1]
    max_price = prices.max()
    min_price = prices.min()
    avg_price = prices.mean()
    std_price = prices.std()

    # Drop from peak (0–40 pts)
    drop_pct   = ((max_price - current) / max_price * 100) if max_price > 0 else 0
    drop_score = min(40, drop_pct * 1.5)

    # Below average (0–30 pts)
    below_avg  = max(0, (avg_price - current) / avg_price * 100) if avg_price > 0 else 0
    avg_score  = min(30, below_avg * 1.5)

    # Recent downtrend (0–20 pts)  — negative slope = dropping = good
    if len(prices) >= 3:
        slope = np.polyfit(range(len(prices)), prices.values, 1)[0]
        trend_score = min(20, max(0, -slope * 5))
    else:
        trend_score = 0

    # Low volatility near bottom (0–10 pts)
    near_min   = 1 - ((current - min_price) / (max_price - min_price + 1e-9))
    vol_score  = 10 * near_min

    total = int(drop_score + avg_score + trend_score + vol_score)
    total = max(0, min(100, total))

    if total >= 75:   label, css = "🔥 HOT DEAL",   "deal-hot"
    elif total >= 50: label, css = "✅ GOOD DEAL",  "deal-good"
    elif total >= 25: label, css = "👁 FAIR",        "deal-fair"
    else:             label, css = "⏳ WATCH",       "deal-watch"

    return {
        "score": total, "label": label, "css": css,
        "drop_pct": round(drop_pct, 1),
        "below_avg_pct": round(below_avg, 1),
    }

def linear_forecast(history_df: pd.DataFrame, days_ahead: int = 14):
    """Forecast next N days using linear regression."""
    df = history_df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])
    df["t"] = (df["date"] - df["date"].min()).dt.days
    prices = df["price"].astype(float).values
    t_vals = df["t"].values

    if len(t_vals) < 2:
        return None

    coeffs = np.polyfit(t_vals, prices, 1)
    last_date = df["date"].max()
    last_t    = t_vals[-1]

    future_dates = [last_date + timedelta(days=i) for i in range(1, days_ahead + 1)]
    future_t     = [last_t + i for i in range(1, days_ahead + 1)]
    future_prices = [np.polyval(coeffs, t) for t in future_t]

    return pd.DataFrame({"date": future_dates, "price": future_prices, "type": "Forecast"})

def price_stats(history_df: pd.DataFrame) -> dict:
    if history_df is None or history_df.empty:
        return {}
    p = history_df["price"].astype(float)
    return {
        "current": float(p.iloc[-1]) if len(p) else None,
        "min":     float(p.min()),
        "max":     float(p.max()),
        "avg":     float(p.mean()),
        "std":     float(p.std()) if len(p) > 1 else 0,
        "total_drop_pct": round((p.max() - p.iloc[-1]) / p.max() * 100, 1) if p.max() > 0 else 0,
    }


# ─────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="pw-title" style="font-size:1.4rem">📡 PriceWatch Pro</p>', unsafe_allow_html=True)
    st.markdown('<p class="pw-subtitle">eBay Intelligence Suite</p>', unsafe_allow_html=True)
    st.divider()

    if st.button("🔄 Refresh Cache", use_container_width=True):
        refresh_data()
        st.toast("Cache cleared!", icon="✅")

    st.divider()
    st.markdown("**⚙️ Forecast Window**")
    forecast_days = st.slider("Days to forecast", 7, 60, 14, step=7)

    st.divider()
    st.markdown("**🎯 Global Target Alert**")
    global_alert_pct = st.number_input("Alert when price drops by (%)", min_value=1, max_value=90, value=10)

    st.divider()
    st.caption("Background scraper must run separately.")
    st.caption(f"Last UI load: {datetime.now().strftime('%H:%M:%S')}")


# ─────────────────────────────────────────────
#  Page: Dashboard (new home page)
# ─────────────────────────────────────────────
def dashboard_page():
    st.markdown('<p class="pw-title">Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="pw-subtitle">Your portfolio at a glance</p>', unsafe_allow_html=True)
    st.divider()

    products_df = fetch_monitored_products()
    if products_df.empty:
        st.info("No products tracked yet. Head to **Product Search** to add some!")
        return

    # Aggregate stats
    all_stats = []
    for _, product in products_df.iterrows():
        h = fetch_price_history(product["id"])
        s = price_stats(h)
        d = compute_deal_score(h)
        if s:
            s["title"]      = product["title"]
            s["id"]         = product["id"]
            s["deal_score"] = d["score"]
            s["deal_label"] = d["label"]
            s["deal_css"]   = d["css"]
            all_stats.append(s)

    if not all_stats:
        st.info("Awaiting first scrape results.")
        return

    stats_df = pd.DataFrame(all_stats)

    # ── KPI Row ──
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Products Tracked", len(products_df))
    with col2:
        avg_drop = stats_df["total_drop_pct"].mean()
        st.metric("Avg Drop from Peak", f"{avg_drop:.1f}%")
    with col3:
        hot = (stats_df["deal_score"] >= 75).sum()
        st.metric("🔥 Hot Deals", hot)
    with col4:
        total_savings = (stats_df["max"] - stats_df["current"]).sum()
        st.metric("Total Savings vs Peak", f"${total_savings:,.2f}")
    with col5:
        cheapest = stats_df.loc[stats_df["current"].idxmin(), "title"] if not stats_df.empty else "—"
        st.metric("Cheapest Item", cheapest[:22] + "…" if len(cheapest) > 22 else cheapest)

    st.divider()

    # ── Best Deals Table ──
    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.subheader("🏆 Best Deals Right Now")
        display = stats_df.sort_values("deal_score", ascending=False)[
            ["title", "current", "min", "max", "total_drop_pct", "deal_label"]
        ].head(8).copy()
        display.columns = ["Product", "Current ($)", "Min ($)", "Max ($)", "Drop from Peak (%)", "Deal"]
        display["Current ($)"]       = display["Current ($)"].map("${:.2f}".format)
        display["Min ($)"]           = display["Min ($)"].map("${:.2f}".format)
        display["Max ($)"]           = display["Max ($)"].map("${:.2f}".format)
        display["Drop from Peak (%)"] = display["Drop from Peak (%)"].map("{:.1f}%".format)
        st.dataframe(display, use_container_width=True, hide_index=True)

    with col_right:
        st.subheader("📊 Deal Score Distribution")
        bins = [0, 25, 50, 75, 101]
        labels = ["Watch", "Fair", "Good", "Hot"]
        stats_df["tier"] = pd.cut(stats_df["deal_score"].fillna(0), bins=bins, labels=labels, right=False)
        tier_counts = stats_df["tier"].value_counts().reindex(labels, fill_value=0).reset_index()
        tier_counts.columns = ["Tier", "Count"]
        color_map = {"Watch": "#6b7280", "Fair": "#3b82f6", "Good": "#f59e0b", "Hot": "#ff4b4b"}
        fig = px.bar(
            tier_counts, x="Tier", y="Count",
            color="Tier", color_discrete_map=color_map,
            template="plotly_dark"
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False, margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Portfolio Price Timeline ──
    st.subheader("📈 Portfolio Price Timeline (All Products)")
    all_history = []
    for _, product in products_df.iterrows():
        h = fetch_price_history(product["id"])
        if h is not None and not h.empty:
            h = h.copy()
            h["product"] = product["title"][:40]
            all_history.append(h)

    if all_history:
        combined = pd.concat(all_history)
        combined["date"] = pd.to_datetime(combined["date"])
        fig2 = px.line(
            combined, x="date", y="price", color="product",
            markers=True, template="plotly_dark",
            labels={"price": "Price ($)", "date": "Date", "product": "Product"}
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig2, use_container_width=True)


# ─────────────────────────────────────────────
#  Page: Product Search
# ─────────────────────────────────────────────
def product_search_page():
    st.markdown('<p class="pw-title">Product Search</p>', unsafe_allow_html=True)
    st.markdown('<p class="pw-subtitle">Scrape eBay and add listings to your watchlist</p>', unsafe_allow_html=True)
    st.divider()

    if "results_df" not in st.session_state:
        st.session_state.results_df = pd.DataFrame()

    # ── Search Bar ──
    col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
    with col1:
        keyword = st.text_input("Keyword", placeholder="e.g. RTX 4090, MacBook Pro M3…", label_visibility="collapsed")
    with col2:
        search_clicked = st.button("🔍 Search eBay", use_container_width=True, type="primary")

    # ── CSV Bulk Import ──
    with st.expander("📥 Bulk Import from CSV"):
        st.caption("Upload a CSV with columns: `title`, `link`, `image_link`")
        uploaded = st.file_uploader("Choose CSV", type="csv", label_visibility="collapsed")
        if uploaded and st.button("Import CSV"):
            try:
                import_df = pd.read_csv(uploaded)
                required = {"title", "link", "image_link"}
                if not required.issubset(import_df.columns):
                    st.error(f"CSV must have columns: {required}")
                else:
                    count = 0
                    for _, row in import_df.iterrows():
                        if db.add_new_product(row["title"], row["link"], row["image_link"]):
                            count += 1
                    st.success(f"✅ Imported {count} products!")
                    refresh_data()
            except Exception as e:
                st.error(f"Import failed: {e}")

    # ── Run Search ──
    if search_clicked and keyword:
        with st.spinner(f"Scraping eBay for **{keyword}**…"):
            results = scrape_search_page(keyword)
            if not results:
                st.warning("No results found for that keyword.")
            else:
                df = pd.DataFrame(results)
                if "select" not in df.columns:
                    df.insert(0, "select", False)
                st.session_state.results_df = df

    # ── Results Table ──
    if not st.session_state.results_df.empty:
        st.divider()
        st.subheader(f"🔍 {len(st.session_state.results_df)} Results")

        # Quick filter
        filter_col, sort_col = st.columns(2)
        with filter_col:
            filter_text = st.text_input("Filter results…", placeholder="Type to filter titles")
        with sort_col:
            sort_by = st.selectbox("Sort by", ["Default", "Price: Low→High", "Price: High→Low"])

        display_df = st.session_state.results_df.copy()
        if filter_text:
            display_df = display_df[display_df["title"].str.contains(filter_text, case=False, na=False)]

        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "select":      st.column_config.CheckboxColumn("Track", width="small"),
                "image_link":  st.column_config.ImageColumn("Image", width="small"),
                "title":       st.column_config.TextColumn("Title", width="large"),
                "price_range": st.column_config.TextColumn("Listed Price"),
                "link":        st.column_config.LinkColumn("Listing", display_text="View →"),
            }
        )

        selected_rows = edited_df[edited_df["select"] == True]
        st.caption(f"{len(selected_rows)} item(s) selected")

        col_add, col_export = st.columns(2)
        with col_add:
            if st.button("➕ Add Selected to Watchlist", type="primary", use_container_width=True):
                if not selected_rows.empty:
                    count = sum(
                        db.add_new_product(r["title"], r["link"], r["image_link"])
                        for _, r in selected_rows.iterrows()
                    )
                    st.toast(f"Added {count} product(s) ✅")
                    refresh_data()
                else:
                    st.warning("Select at least one item.")
        with col_export:
            if st.button("📤 Export Results to CSV", use_container_width=True):
                csv_data = display_df.drop(columns=["select"], errors="ignore").to_csv(index=False)
                st.download_button(
                    "⬇️ Download CSV", csv_data, "ebay_search_results.csv", "text/csv",
                    use_container_width=True
                )


# ─────────────────────────────────────────────
#  Page: Price History & Analytics
# ─────────────────────────────────────────────
def price_history_page():
    st.markdown('<p class="pw-title">Price Analytics</p>', unsafe_allow_html=True)
    st.markdown('<p class="pw-subtitle">Deep-dive trends, forecasts, and deal scoring</p>', unsafe_allow_html=True)
    st.divider()

    products_df = fetch_monitored_products()
    if products_df.empty:
        st.info("No products tracked. Go to **Product Search** first.")
        return

    # ── Filters ──
    with st.expander("🔽 Filter & Sort Watchlist", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filter_title = st.text_input("Filter by name", placeholder="Product name…")
        with col_f2:
            deal_filter = st.multiselect("Deal tier", ["🔥 HOT DEAL", "✅ GOOD DEAL", "👁 FAIR", "⏳ WATCH", "Insufficient Data"])
        with col_f3:
            sort_watchlist = st.selectbox("Sort by", ["Default", "Deal Score ↓", "Current Price ↑", "Current Price ↓", "Drop % ↓"])

    # ── Track chart state ──
    if "active_chart" not in st.session_state:
        st.session_state.active_chart = None
    if "target_prices" not in st.session_state:
        st.session_state.target_prices = {}

    # ── Export All ──
    if st.button("📤 Export Watchlist to CSV", use_container_width=False):
        rows = []
        for _, p in products_df.iterrows():
            s = price_stats(fetch_price_history(p["id"]))
            d = compute_deal_score(fetch_price_history(p["id"]))
            rows.append({"title": p["title"], "link": p["link"],
                         **s, "deal_score": d["score"], "deal_label": d["label"]})
        csv = pd.DataFrame(rows).to_csv(index=False)
        st.download_button("⬇️ Download", csv, "watchlist_export.csv", "text/csv")

    st.divider()

    # ── Build enriched list for sorting ──
    enriched = []
    for _, product in products_df.iterrows():
        h = fetch_price_history(product["id"])
        s = price_stats(h)
        d = compute_deal_score(h)
        enriched.append((product, h, s, d))

    # Apply filters
    if filter_title:
        enriched = [(p, h, s, d) for p, h, s, d in enriched if filter_title.lower() in p["title"].lower()]
    if deal_filter:
        enriched = [(p, h, s, d) for p, h, s, d in enriched if d["label"] in deal_filter or (not s and "Insufficient Data" in deal_filter)]

    # Apply sort
    if sort_watchlist == "Deal Score ↓":
        enriched.sort(key=lambda x: x[3]["score"] or -1, reverse=True)
    elif sort_watchlist == "Current Price ↑":
        enriched.sort(key=lambda x: x[2].get("current") or float("inf"))
    elif sort_watchlist == "Current Price ↓":
        enriched.sort(key=lambda x: x[2].get("current") or 0, reverse=True)
    elif sort_watchlist == "Drop % ↓":
        enriched.sort(key=lambda x: x[2].get("total_drop_pct") or 0, reverse=True)

    # ── Render each product card ──
    for product, history_df, stats, deal in enriched:
        with st.container():
            st.markdown('<div class="pw-card">', unsafe_allow_html=True)

            col_img, col_info, col_metrics, col_actions = st.columns([1, 2.5, 2, 1.2], vertical_alignment="center")

            with col_img:
                st.image(product.get("image_link", ""), use_container_width=True)

            with col_info:
                # Title + deal badge
                badge_html = f'<span class="deal-badge {deal["css"]}">{deal["label"]}</span>' if deal["score"] is not None else ""
                st.markdown(f"### {product['title'][:60]}")
                st.markdown(badge_html, unsafe_allow_html=True)
                st.caption(f"[View on eBay]({product['link']})")

                # Target price alert UI
                pid = product["id"]
                target_key = f"target_{pid}"
                current_target = st.session_state.target_prices.get(pid)
                new_target = st.number_input(
                    "🎯 Target Price ($)", min_value=0.0, value=float(current_target or 0.0),
                    step=1.0, key=target_key, help="Get a visual badge when price hits this target"
                )
                st.session_state.target_prices[pid] = new_target if new_target > 0 else None

                # Fire alert badge
                if current_target and stats.get("current") and stats["current"] <= current_target:
                    st.markdown('<span class="target-hit">🎯 TARGET PRICE HIT!</span>', unsafe_allow_html=True)

                # Deal score meter
                if deal["score"] is not None:
                    score_pct = deal["score"] / 100
                    bar_color = "#ff4b4b" if deal["score"] >= 75 else ("#f59e0b" if deal["score"] >= 50 else ("#3b82f6" if deal["score"] >= 25 else "#6b7280"))
                    st.markdown(
                        f"""<div style="background:#1e2733;border-radius:6px;height:6px;margin-top:6px">
                          <div style="background:{bar_color};width:{deal['score']}%;height:6px;border-radius:6px"></div>
                        </div>
                        <span style="color:{bar_color};font-size:0.78rem;font-family:'JetBrains Mono'">Deal Score: {deal['score']}/100 | -{deal.get('drop_pct',0)}% from peak</span>""",
                        unsafe_allow_html=True
                    )

            with col_metrics:
                if stats:
                    m1, m2 = st.columns(2)
                    with m1:
                        if len(history_df) >= 2:
                            h_sorted  = history_df.sort_values("date")
                            curr      = float(h_sorted.iloc[-1]["price"])
                            prev      = float(h_sorted.iloc[-2]["price"])
                            st.metric("Current", f"${curr:.2f}", f"${curr - prev:.2f}", delta_color="inverse")
                        elif len(history_df) == 1:
                            st.metric("Current", f"${stats['current']:.2f}", "New")
                        else:
                            st.metric("Current", "Pending…", "Awaiting Scrape", delta_color="off")
                    with m2:
                        st.metric("Min / Max", f"${stats['min']:.2f}", f"Max ${stats['max']:.2f}", delta_color="off")
                    m3, m4 = st.columns(2)
                    with m3:
                        st.metric("Avg Price", f"${stats['avg']:.2f}")
                    with m4:
                        st.metric("Volatility (σ)", f"${stats['std']:.2f}")
                else:
                    st.metric("Current", "Pending…", delta_color="off")

            with col_actions:
                if st.button("📉 Chart", key=f"chart_{pid}", use_container_width=True):
                    st.session_state.active_chart = pid if st.session_state.active_chart != pid else None
                if st.button("🗑 Untrack", key=f"del_{pid}", use_container_width=True):
                    db.delete_product(pid)
                    st.toast("Removed from watchlist.")
                    refresh_data()
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        # ── Expanded Chart Panel ──
        if st.session_state.active_chart == product["id"]:
            if history_df is None or len(history_df) < 2:
                st.warning("Not enough data. Wait for another scrape cycle.")
            else:
                with st.container():
                    tab_trend, tab_forecast, tab_stats, tab_raw = st.tabs([
                        "📈 Trend + SMA", "🔮 Price Forecast", "📊 Statistics", "🗂 Raw Data"
                    ])

                    with tab_trend:
                        hdf = history_df.sort_values("date").copy()
                        hdf["SMA-3"]  = hdf["price"].rolling(3,  min_periods=1).mean()
                        hdf["SMA-7"]  = hdf["price"].rolling(7,  min_periods=1).mean()
                        hdf["EMA-5"]  = hdf["price"].ewm(span=5, adjust=False).mean()

                        melted = hdf.melt(
                            id_vars=["date"],
                            value_vars=["price", "SMA-3", "SMA-7", "EMA-5"],
                            var_name="Metric", value_name="Price (USD)"
                        )
                        color_map = {
                            "price":  "#b0c4de",
                            "SMA-3":  "#3b82f6",
                            "SMA-7":  "#818cf8",
                            "EMA-5":  "#f59e0b",
                        }
                        fig = px.line(melted, x="date", y="Price (USD)", color="Metric",
                                      markers=True, template="plotly_dark",
                                      color_discrete_map=color_map,
                                      title=f"Price History — {product['title'][:50]}")

                        # Add min/max annotations
                        min_row = hdf.loc[hdf["price"].idxmin()]
                        max_row = hdf.loc[hdf["price"].idxmax()]
                        fig.add_annotation(x=min_row["date"], y=float(min_row["price"]),
                                           text=f"Low ${float(min_row['price']):.2f}",
                                           showarrow=True, arrowhead=2, font=dict(color="#22c55e"))
                        fig.add_annotation(x=max_row["date"], y=float(max_row["price"]),
                                           text=f"High ${float(max_row['price']):.2f}",
                                           showarrow=True, arrowhead=2, font=dict(color="#ff4b4b"))

                        # Target price line
                        tp = st.session_state.target_prices.get(product["id"])
                        if tp:
                            fig.add_hline(y=tp, line_dash="dot", line_color="#22c55e",
                                          annotation_text=f"Target ${tp:.2f}", annotation_position="top right")

                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            hovermode="x unified", xaxis_title="Date", yaxis_title="Price ($)",
                            legend=dict(orientation="h", y=1.1)
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    with tab_forecast:
                        forecast_df = linear_forecast(history_df, days_ahead=forecast_days)
                        if forecast_df is not None:
                            hdf2 = history_df.sort_values("date").copy()
                            hdf2["type"] = "Historical"
                            forecast_df["type"] = "Forecast"
                            combined = pd.concat([hdf2[["date", "price", "type"]], forecast_df])
                            combined["date"] = pd.to_datetime(combined["date"])

                            fig_f = go.Figure()
                            hist_part = combined[combined["type"] == "Historical"]
                            fore_part = combined[combined["type"] == "Forecast"]

                            fig_f.add_trace(go.Scatter(
                                x=hist_part["date"], y=hist_part["price"].astype(float),
                                mode="lines+markers", name="Historical",
                                line=dict(color="#3b82f6", width=2)
                            ))
                            fig_f.add_trace(go.Scatter(
                                x=fore_part["date"], y=fore_part["price"].astype(float),
                                mode="lines+markers", name="Forecast",
                                line=dict(color="#f59e0b", width=2, dash="dash"),
                                marker=dict(symbol="diamond")
                            ))

                            # Confidence band (±1 std)
                            std_val = stats.get("std", 0)
                            fig_f.add_trace(go.Scatter(
                                x=list(fore_part["date"]) + list(fore_part["date"])[::-1],
                                y=list((fore_part["price"].astype(float) + std_val)) + list((fore_part["price"].astype(float) - std_val))[::-1],
                                fill="toself", fillcolor="rgba(245,158,11,0.1)",
                                line=dict(color="rgba(0,0,0,0)"), name="Confidence Band"
                            ))

                            fig_f.update_layout(
                                template="plotly_dark",
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                hovermode="x unified", title=f"{forecast_days}-Day Forecast",
                                xaxis_title="Date", yaxis_title="Price ($)",
                                legend=dict(orientation="h", y=1.1)
                            )
                            st.plotly_chart(fig_f, use_container_width=True)

                            predicted_end = fore_part["price"].iloc[-1]
                            direction = "📉 DOWN" if predicted_end < stats["current"] else "📈 UP"
                            st.info(f"Model predicts price will be **${predicted_end:.2f}** in {forecast_days} days ({direction}) — based on linear regression. Not financial advice.")
                        else:
                            st.warning("Not enough data to generate a forecast.")

                    with tab_stats:
                        if stats:
                            s_col1, s_col2, s_col3 = st.columns(3)
                            s_col1.metric("Current Price",  f"${stats['current']:.2f}")
                            s_col1.metric("Min Price",      f"${stats['min']:.2f}")
                            s_col2.metric("Max Price",      f"${stats['max']:.2f}")
                            s_col2.metric("Avg Price",      f"${stats['avg']:.2f}")
                            s_col3.metric("Std Deviation",  f"${stats['std']:.2f}")
                            s_col3.metric("Drop from Peak", f"{stats['total_drop_pct']}%")

                            # Histogram
                            hdf3 = history_df.copy()
                            hdf3["price"] = hdf3["price"].astype(float)
                            fig_hist = px.histogram(hdf3, x="price", nbins=20,
                                                    template="plotly_dark", title="Price Distribution",
                                                    color_discrete_sequence=["#3b82f6"])
                            fig_hist.update_layout(
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                margin=dict(t=40, l=0, r=0, b=0)
                            )
                            st.plotly_chart(fig_hist, use_container_width=True)

                    with tab_raw:
                        raw_display = history_df.sort_values("date", ascending=False).copy()
                        raw_display["price"] = raw_display["price"].astype(float).map("${:.2f}".format)
                        st.dataframe(raw_display, use_container_width=True, hide_index=True)
                        csv_raw = history_df.to_csv(index=False)
                        st.download_button(
                            "⬇️ Download Raw Data", csv_raw,
                            f"price_history_{product['id']}.csv", "text/csv"
                        )

        st.divider()


# ─────────────────────────────────────────────
#  Page: Alerts Log  (reads from DB if available)
# ─────────────────────────────────────────────
def alerts_page():
    st.markdown('<p class="pw-title">Alerts & Notifications</p>', unsafe_allow_html=True)
    st.markdown('<p class="pw-subtitle">Products that hit your target prices</p>', unsafe_allow_html=True)
    st.divider()

    products_df = fetch_monitored_products()
    if products_df.empty:
        st.info("No products tracked yet.")
        return

    alerts = []
    for _, product in products_df.iterrows():
        h = fetch_price_history(product["id"])
        stats = price_stats(h)
        target = st.session_state.get("target_prices", {}).get(product["id"])

        if stats.get("current") is not None:
            # Check global drop alert
            if stats["total_drop_pct"] >= global_alert_pct:
                alerts.append({
                    "Product":    product["title"][:50],
                    "Alert Type": f"🔻 Drop ≥{global_alert_pct}%",
                    "Current":    f"${stats['current']:.2f}",
                    "Max Was":    f"${stats['max']:.2f}",
                    "Drop %":     f"{stats['total_drop_pct']}%",
                    "Status":     "🔴 ACTIVE",
                })
            # Check target price
            if target and stats["current"] <= target:
                alerts.append({
                    "Product":    product["title"][:50],
                    "Alert Type": "🎯 Target Price Hit",
                    "Current":    f"${stats['current']:.2f}",
                    "Max Was":    f"${stats['max']:.2f}",
                    "Drop %":     f"{stats['total_drop_pct']}%",
                    "Status":     "✅ TARGET HIT",
                })

    if alerts:
        st.success(f"⚠️ {len(alerts)} active alert(s) triggered!")
        alerts_df = pd.DataFrame(alerts)
        st.dataframe(alerts_df, use_container_width=True, hide_index=True)
        csv_alerts = alerts_df.to_csv(index=False)
        st.download_button("⬇️ Export Alerts", csv_alerts, "alerts.csv", "text/csv")
    else:
        st.info(f"No alerts triggered. Watching for drops ≥{global_alert_pct}% and per-product target prices.")

    st.divider()
    st.subheader("📋 Full Portfolio Snapshot")
    snapshot = []
    for _, product in products_df.iterrows():
        h = fetch_price_history(product["id"])
        stats = price_stats(h)
        deal  = compute_deal_score(h)
        snapshot.append({
            "Product":      product["title"][:45],
            "Current ($)":  f"${stats['current']:.2f}" if stats.get("current") else "—",
            "Min ($)":      f"${stats['min']:.2f}" if stats.get("min") else "—",
            "Max ($)":      f"${stats['max']:.2f}" if stats.get("max") else "—",
            "Drop %":       f"{stats.get('total_drop_pct', 0):.1f}%" if stats else "—",
            "Deal Score":   deal["score"] if deal["score"] else "—",
            "Tier":         deal["label"],
        })
    if snapshot:
        st.dataframe(pd.DataFrame(snapshot), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────
#  Navigation
# ─────────────────────────────────────────────
dashboard_pg = st.Page(dashboard_page,      title="Dashboard",       icon="🏠")
search_pg    = st.Page(product_search_page, title="Product Search",   icon="🔍")
history_pg   = st.Page(price_history_page,  title="Price Analytics",  icon="📊")
alerts_pg    = st.Page(alerts_page,         title="Alerts",           icon="🔔")

pg = st.navigation([dashboard_pg, search_pg, history_pg, alerts_pg])
pg.run()
import streamlit as st
import pandas as pd
import plotly.express as px
from playwright.sync_api import sync_playwright

import database as db
from product_search import scrape_search_page

# ---------- Page Configuration ----------
st.set_page_config(page_title="eBay Price Monitor", page_icon="🛒", layout="wide")


# ---------- Caching & Data Management ----------
@st.cache_data(ttl=600)
def fetch_monitored_products():
    return db.get_monitored_products()


@st.cache_data(ttl=600)
def fetch_price_history(product_id):
    return db.get_product_price_history(product_id)


def refresh_data():
    fetch_monitored_products.clear()
    fetch_price_history.clear()


# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("🔄 Force Refresh Data", use_container_width=True):
        refresh_data()
        st.toast("Data cache cleared!")

    st.divider()
    st.caption("Background scraper must run separately to update prices.")


# ---------- Page 1: Product Search ----------
def product_search_page():
    st.title("🛒 Product Search")
    st.write("Search eBay and select products to track.")

    # Initialize session state for search results
    if "results_df" not in st.session_state:
        st.session_state.results_df = pd.DataFrame()

    with st.container():
        col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
        with col1:
            keyword = st.text_input("Enter product keyword", placeholder="e.g. MacBook Pro M2")
        with col2:
            search_clicked = st.button("Search", use_container_width=True)

    if search_clicked and keyword:
        with st.spinner(f"Scraping eBay for '{keyword}'..."):
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=False)
                page = browser.new_page()
                results = scrape_search_page(keyword,page)

                if not results:
                    st.warning("Sorry, no results found!")
                else:
                    df = pd.DataFrame(results)
                    # Insert checkbox column
                    if "select" not in df.columns:
                        df.insert(0, "select", False)
                    st.session_state.results_df = df

    if not st.session_state.results_df.empty:
        st.divider()
        st.subheader("🔍 Search Results")

        edited_df = st.data_editor(
            st.session_state.results_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "select": st.column_config.CheckboxColumn("Track", width="small"),
                "image_link": st.column_config.ImageColumn("Image", width="small"),
                "title": st.column_config.TextColumn("Title", width="large"),
                "price_range": st.column_config.TextColumn("Listed Price"),
                "link": st.column_config.LinkColumn("Listing", display_text="View on eBay"),
            }
        )

        selected_rows = edited_df[edited_df["select"]]

        if st.button("➕ Add Selected to Monitor", type="primary"):
            if not selected_rows.empty:
                success_count = 0
                for index, product in selected_rows.iterrows():
                    # Add to products table
                    added = db.add_new_product(product["title"], product["link"], product["image_link"])
                    if added:
                        success_count += 1

                if success_count > 0:
                    st.toast(f"Added {success_count} product(s) to monitor list! 🎉")
                    refresh_data()  # Clear cache so new items show up in Price History immediately
            else:
                st.warning("Please check the box next to at least one item.")


# ---------- Page 2: Price History ----------
def price_history_page():
    st.title("📊 Price Analytics")
    st.write("Analyze trends and track price drops for your saved items.")
    st.divider()

    # Fetch data
    products_df = fetch_monitored_products()

    if products_df.empty:
        st.info("You aren't tracking any products yet! Go to the Search page to add some.")
        return

    # Track which chart is currently open
    if "active_chart" not in st.session_state:
        st.session_state.active_chart = None

    for index, product in products_df.iterrows():
        col_img, col_info, col_metrics, col_actions = st.columns([1, 2.5, 1.5, 1], vertical_alignment="center")

        with col_img:
            # Display image, fallback to empty string if missing
            st.image(product.get("image_link", ""), use_container_width=True)

        with col_info:
            st.subheader(product["title"])
            st.caption(f"[View original listing on eBay]({product['link']})")

        with col_metrics:
            history_df = fetch_price_history(product['id'])

            if len(history_df) >= 2:
                # Calculate Delta
                history_df = history_df.sort_values(by="date")
                current_price = float(history_df.iloc[-1]['price'])
                previous_price = float(history_df.iloc[-2]['price'])
                price_diff = current_price - previous_price

                st.metric(
                    label="Current Price",
                    value=f"${current_price:.2f}",
                    delta=f"${price_diff:.2f}",
                    delta_color="inverse"  # Green for price drops, Red for increases
                )
            elif len(history_df) == 1:
                # Only one data point exists
                current_price = float(history_df.iloc[0]['price'])
                st.metric(label="Current Price", value=f"${current_price:.2f}", delta="New")
            else:
                # Product added to DB, but scraper.py hasn't checked it yet
                st.metric(label="Current Price", value="Pending...", delta="Awaiting Scrape", delta_color="off")

        with col_actions:
            if st.button("📉 View Trend", key=f"btn_chart_{product['id']}", use_container_width=True):
                st.session_state.active_chart = product['id'] if st.session_state.active_chart != product[
                    'id'] else None

            if st.button("🗑️ Untrack", key=f"btn_del_{product['id']}", use_container_width=True):
                db.delete_product(product['id'])
                st.toast("Product untracked.")
                refresh_data()
                st.rerun()

        # Display Plotly Chart if activated
        if st.session_state.active_chart == product['id']:
            if len(history_df) < 2:
                st.warning("Not enough data to draw a trend chart. Wait for the background scraper to run again.")
            else:
                with st.container():
                    # Calculate 3-point Simple Moving Average
                    history_df['Trend (SMA)'] = history_df['price'].rolling(window=3, min_periods=1).mean()

                    # Melt dataframe for Plotly multi-line charting
                    plot_df = history_df.melt(id_vars=['date'], value_vars=['price', 'Trend (SMA)'],
                                              var_name='Metric', value_name='Price (USD)')

                    fig = px.line(
                        plot_df,
                        x="date",
                        y="Price (USD)",
                        color="Metric",
                        markers=True,
                        title="Historical Price Trend",
                        color_discrete_map={"price": "#B0C4DE", "Trend (SMA)": "#FF4B4B"}
                    )

                    fig.update_layout(xaxis_title="Date Recorded", yaxis_title="Price ($)", hovermode="x unified")
                    st.plotly_chart(fig, use_container_width=True)

        st.divider()


# ---------- Modern Native Routing ----------
search_page = st.Page(product_search_page, title="Product Search", icon="🛒")
history_page = st.Page(price_history_page, title="Price History", icon="📊")

pg = st.navigation([search_page, history_page])
pg.run()
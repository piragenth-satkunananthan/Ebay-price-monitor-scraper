import re

import pandas as pd
from playwright.sync_api import sync_playwright
import sqlite3
conn = sqlite3.connect("ebay_scraper.db", check_same_thread=False)
cursor = conn.cursor()

#from seleniumbase import sb_cdp
# from bs4 import BeautifulSoup
# from selenium.webdriver.support.expected_conditions import title_is
# from seleniumbase.core.detect_b_ver import brave_on_windows_path



def main():
    url_id_list=retrive_product_link_from_db()


    for index,row in url_id_list.iterrows():
        url = str(row['url'])
        id = int(row['id'])
        # print(url)
        product_name,product_price=scrape_product(url)
        add_price_history_to_db(id,product_price)


def scrape_product(url):
#    sb = sb_cdp.Chrome()
#     endpoint_url = sb.get_endpoint_url()
    with sync_playwright() as p:
        # browser = p.chromium.connect_over_cdp(endpoint_url)
        browser = p.chromium.launch(headless=False)
        # context = browser.contexts[0]
        # page = context.pages[0]
        page = browser.new_page()
        page.goto(url)


        # sb.solve_captcha()
        # page.wait_for_selector("h1.x-item-title__mainTitle")
        product_name = page.locator("div.x-item-title").inner_text()
        # product_price = float(page.locator('div.x-price-primary').nth(0).locator('.ux-textspans').first.inner_text().split('$')[-1])
        product_price = page.query_selector("span.x-price-approx__price")

        if product_price:
            product_price = product_price.inner_text().split("$")[-1]
        else:
            product_price = page.locator('div.x-price-primary').nth(0).locator('.ux-textspans').first.inner_text().split('$')[-1]
        # print(product_name,product_price)
        product_price = float(re.sub(r'[^0-9.]', '', product_price))
        print(product_price)

    return (product_name, product_price)

# print(scrape_product("https://www.ebay.com/itm/127746082819"))

def retrive_product_link_from_db():
    # Use a real URL from your database


    # This query joins the tables so you get the title AND the prices in one go
    query = """
            SELECT id,url from products;
            """

    product_history = pd.read_sql(query, conn)



    return product_history



def add_price_history_to_db(product_id,price):
    cursor.execute("insert into price_history(product_id,price) values (?,?)", (product_id,price))

    conn.commit()


main()



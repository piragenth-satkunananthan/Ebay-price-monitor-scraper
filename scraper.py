import re

import pandas as pd
from playwright.sync_api import sync_playwright
import database as db

#from seleniumbase import sb_cdp
# from bs4 import BeautifulSoup
# from selenium.webdriver.support.expected_conditions import title_is
# from seleniumbase.core.detect_b_ver import brave_on_windows_path



def main():
    url_id_list=db.retrive_product_link_from_db()

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        # page.wait_for_selector("div.x-price-primary")

        for index,row in url_id_list.iterrows():
            url = str(row['url'])
            id = int(row['id'])
            # print(url)
            try:
                product_name,product_price=scrape_product(url,page)
                db.add_price_history_to_db(id,product_price)
            except:
                continue
        browser.close()

def scrape_product(url,page):
#    sb = sb_cdp.Chrome()
#     endpoint_url = sb.get_endpoint_url()
    # browser = p.chromium.connect_over_cdp(endpoint_url)
    # browser = p.chromium.launch(headless=False)
    # context = browser.contexts[0]
    # page = context.pages[0]
    # page = browser.new_page()
    page.goto(url)


    # sb.solve_captcha()
    # page.wait_for_selector("h1.x-item-title__mainTitle")
    try:
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

    except:
        print("no price found")



# print(scrape_product("https://www.ebay.com/itm/127746082819"))





main()



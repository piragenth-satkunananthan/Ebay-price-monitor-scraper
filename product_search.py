from playwright.sync_api import sync_playwright

def scrape_search_page(keyword):
    print('search')
    product_name_list = []
    url = f"https://www.ebay.com/sch/i.html?_nkw={keyword}"
    # sb = sb_cdp.Chrome()
    # endpoint_url = sb.get_endpoint_url()
    with sync_playwright() as p:
        # browser = p.chromium.connect_over_cdp(endpoint_url)
        browser = p.firefox.launch(headless=True)

        # context = browser.contexts[0]
        # page = context.pages[0]
        page = browser.new_page()
        page.goto(url)
        # sb.solve_captcha()
        page.wait_for_selector(".s-footer-notes--entry")
        # page.wait_for_timeout(10)

        print("su-card-container__content available")
        products = page.locator(".su-card-container")
        for i in range(products.count()-1):
            if i <= 2:
                continue
            product = products.nth(i)
            link = product.locator("a.s-card__link").nth(1).get_attribute("href").split("?")[0]
            # price_range = product.locator("div.su-card-container__attributes__primary").locator("div.s-card__attribute-row").locator("span.s-card__price").inner_text() #problem
            price_range = product.locator("span.s-card__price").all_inner_texts()
            price_range = " ".join(price_range)
            # print(price_range)
            # price_range = "".join(price_range)
            # if price_range.split("to"):
            #     price_range = price_range.replace("$","")
            #     price_range = price_range.split("to")
            title = product.locator("div.s-card__title").locator("span.primary").inner_text()
            # image_link = product.locator("su-image").locator("a.s-card__link").locator("img.s-card__image").get_attribute("src")
            image_link = product.locator("img.s-card__image").get_attribute("src")

            # print(image_link,title,link,price_range)
            # product_name_list.append(title)
            product_name_list.append({"title": title,
                                      "link": link,
                                      "price_range": price_range,
                                      "image_link": image_link
                                      })
            browser.close()

        return product_name_list
# print(scrape_search_page("pencil"))

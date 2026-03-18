import database as db
from scraper import scrape_product

# title = "test"
# image_link = "https://www.google.com"
# url = "https://www.ebay.com/itm/188169921976"
# price = 20
# if db.add_new_price_history(url,price):
#     print("success")
# else:
#     print("fail")
#
# if db.add_new_product(title, url, image_link):
#     print("success")
# else:
#     print("fail")

print(scrape_product("https://www.ebay.com/itm/177947008994"))
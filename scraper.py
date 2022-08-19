from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
import sqlite3
import numpy as np

options = Options()
options.headless = True
options.add_argument("--window-size=1920,1200")
driver = webdriver.Chrome(options=options, service=Service(ChromeDriverManager().install()))

BASE_URL = "https://ocs.ca/collections/"
# need to determine if these categories are sufficient, as they do not overlap 1:1 with Dutchie
CATEGORIES = ["dried-flower", "pre-rolls", "vapes", "extracts", "edibles", "beverages", "topicals", "seeds",
              "accessories"]

OCS_KEY_PRODUCT_CELL = "product-tile"
OCS_KEY_PRODUCT_BRAND = "product-tile__vendor"
OCS_KEY_PRODUCT_NAME = "product-tile__title"
OCS_KEY_PRODUCT_SIZE = "swatch__title"
OCS_KEY_PRODUCT_PRICE = "product-tile__price__main"
OCS_KEY_PRODUCT_STRAINTYPE = "product-tile__plant-type"
OCS_KEY_PRODUCT_CONCENTRATION_CELL = "product-tile__potency-scale"
OCS_KEY_PRODUCT_CONCENTRATION_TEXT = "scale__data"

database_date = time.strftime('%Y%m%d')


class Product:
    def __init__(self, brand, name, sizes, prices, straintype, concentrations_thc, concentrations_cbd):
        self.brand = brand
        self.name = name
        self.sizes = sizes
        self.prices = prices
        self.strainType = straintype
        self.concentrationsThc = concentrations_thc
        self.concentrationsCbd = concentrations_cbd

    def toString(self):
        string_build = self.brand.ljust(30, ' ') + self.name + "(" + self.strainType + ", THC " + \
                       self.concentrationsThc + ", CBD" + self.concentrationsCbd + ")"
        if len(self.sizes) > 0:
            for i in range(len(self.sizes)):
                string_build += "\n" + self.sizes[i].rjust(45, ' ') + self.prices[i].rjust(5, ' ')
        else:
            string_build += self.prices[0]
        return string_build


startTime = time.time()

for category in CATEGORIES:

    print("Beginning scrape of category: " + category)
    categoryStartTime = time.time()

    driver.get(BASE_URL + category + "?load_view=all")

    productList = []

    scrollLevel = 0

    height = int(driver.execute_script("return document.documentElement.scrollHeight"))

    # need to verify this scrolling still works for OCS due to it loading everything on one page
    while scrollLevel < height:
        scrollLevel += 1000
        driver.execute_script("window.scrollTo(500," + str(scrollLevel) + ")")
        time.sleep(0.2)

    cells = driver.find_elements(By.CLASS_NAME, OCS_KEY_PRODUCT_CELL)

    for cell in cells:

        product_sizes = []
        product_prices = []
        product_concentrations_thc = []
        product_concentrations_cbd = []

        product_brand = cell.find_element(By.CLASS_NAME, OCS_KEY_PRODUCT_BRAND).text
        product_name = cell.find_element(By.CLASS_NAME, OCS_KEY_PRODUCT_NAME).text
        # have to grab size list separately as otherwise the list items will go stale when referencing later on
        # cannot grab .text directly due to the plural find_elements method
        product_sizes_list = cell.find_elements(By.CLASS_NAME, OCS_KEY_PRODUCT_SIZE)

        # TODO requires testing
        for size in product_sizes_list:
            size.click()
            product_sizes.append(size.text)
            product_prices.append(cell.find_element(OCS_KEY_PRODUCT_PRICE).text)

        product_straintype = cell.find_element(By.CLASS_NAME, OCS_KEY_PRODUCT_STRAINTYPE).text

        # TODO requires testing
        product_concentration_cell = cell.find_element(By.CLASS_NAME, OCS_KEY_PRODUCT_CONCENTRATION_CELL)
        product_concentrations = product_concentration_cell.find_elements(By.CLASS_NAME,
                                                                          OCS_KEY_PRODUCT_CONCENTRATION_TEXT)
        product_concentrations_thc = product_concentrations[0].text
        product_concentrations_cbd = product_concentrations[1].text

        newProduct = Product(product_brand, product_name, product_sizes, product_prices, product_straintype,
                             product_concentrations_thc, product_concentrations_cbd)
        productList.append(newProduct)

    print(str(len(productList)) + " items found.")

    con = sqlite3.connect("{}.sqlite".format("ocs_" + database_date))
    cur = con.cursor()
    category_sql_friendly = category.replace("-", "")

    cur.execute("DROP TABLE IF EXISTS {}".format(category_sql_friendly))
    cur.execute("CREATE TABLE IF NOT EXISTS {} (brand text, name text, size real, price real, price_per_gram real, "
                "straintype text, concentration text)".format(category_sql_friendly))

    data = []

    for product in productList:
        for index, price in enumerate(product.prices):
            strippedPrice = float(price.strip("$ /g"))
            # TODO need to handle OCS' display method of multipacks (i.e. '12 x 0.6g')
            if len(product.sizes) > 0:
                strippedSize = float(product.sizes[index].strip("x g"))
                # TODO OCS already calculates ppg for us, just grab that value from the page
                pricePerGram = np.round(strippedPrice / strippedSize, 2)
            else:
                strippedSize, pricePerGram = "", ""
            data += [
                (product.brand, product.name, strippedSize, strippedPrice, pricePerGram, product.strainType,
                 product.concentrationsThc, product.concentrationsCbd)
            ]

    cur.executemany('INSERT INTO {} VALUES(?, ?, ?, ?, ?, ?, ?, ?)'.format(category_sql_friendly), data)

    con.commit()
    con.close()
    print("Committed, took " + str(time.time() - float(categoryStartTime)) + " seconds.")

print("Total run took " + str(time.time() - float(startTime)) + " seconds.")

driver.quit()

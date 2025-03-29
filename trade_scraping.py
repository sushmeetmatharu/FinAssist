import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pymongo import MongoClient

# MongoDB Setup
client = MongoClient("mongodb://localhost:27017/")
db = client["StockMarket"]
collection = db["NSEStockData"]

# NSE URLs
live_equity_url = "https://www.nseindia.com/market-data/live-equity-market"

def get_driver():
    """Initializes an undetected Selenium WebDriver with anti-detection measures."""
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    # REMOVE headless mode to debug properly
    # options.add_argument("--headless=new")

    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.166 Safari/537.36"
    )

    driver = uc.Chrome(options=options)
    driver.get("https://www.nseindia.com")  # Open NSE to set cookies
    time.sleep(10)  # Allow time for anti-bot measures to settle
    return driver

def extract_stock_links(driver):
    """Extracts stock symbols and their URLs from the Live Equity Market page."""
    driver.get(live_equity_url)
    time.sleep(10)  # Allow JavaScript to load

    try:
        wait = WebDriverWait(driver, 30)

        # Locate the table body containing stock symbols
        stocks_table = wait.until(
            EC.presence_of_element_located((By.XPATH, "//table[@id='equityStockTable']//tbody"))
        )

        # Extract stock names and URLs (Only top stocks)
        stock_links = []
        rows = stocks_table.find_elements(By.TAG_NAME, "tr")[:5]  # Limit to top 5

        for row in rows:
            try:
                stock_element = row.find_element(By.XPATH, ".//td[1]/a")
                stock_name = stock_element.text.strip()
                stock_url = stock_element.get_attribute("href")
                stock_links.append((stock_name, stock_url))
                print(f"Found stock: {stock_name}")
            except Exception as e:
                print(f"Skipping row due to error: {e}")

        return stock_links

    except Exception as e:
        print(f"Error extracting stock links: {e}")
        return []

def extract_stock_details(driver, stock_name, stock_url):
    """Extracts stock details from its page."""
    driver.get(stock_url)
    time.sleep(10)  # Allow page to load

    stock_data = {
        "Stock Name": stock_name,
        "Stock URL": stock_url,
        "Trade Information": {},
        "Price Information": {},
        "Securities Information": {}
    }

    tables = {
        "Trade Information": "//th[@id='Trade_Information_pg']/ancestor::table/tbody",
        "Price Information": "//th[@id='priceInformationHeading']/ancestor::table/tbody",
        "Securities Information": "//th[@id='Securities_Info_New']/ancestor::table/tbody"
    }

    for table_name, xpath in tables.items():
        try:
            table_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            rows = table_element.find_elements(By.TAG_NAME, "tr")

            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) == 2:
                    key = cells[0].text.strip()
                    value = cells[1].text.strip()
                    stock_data[table_name][key] = value

        except Exception as e:
            print(f"Error extracting {table_name} for {stock_name}: {e}")

    return stock_data

def scrape_nse_data():
    """Main function to extract and store stock data."""
    driver = get_driver()
    stock_links = extract_stock_links(driver)

    if not stock_links:
        print("No stocks found. Exiting script.")
        driver.quit()
        return

    for stock_name, stock_url in stock_links:
        print(f"Scraping data for {stock_name}...")

        try:
            stock_details = extract_stock_details(driver, stock_name, stock_url)
            collection.insert_one(stock_details)
            print(f"Stored data for {stock_name} successfully.")
            print(f"Total records in database: {collection.count_documents({})}\n")

        except Exception as e:
            print(f"Error processing {stock_name}: {e}")

        time.sleep(10)  # Avoid bot detection

    driver.quit()
    print("Data extraction complete.")

scrape_nse_data()

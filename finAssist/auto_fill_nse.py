import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_latest_nse_data(stock_name):
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)

    wait = WebDriverWait(driver, 20)
    driver.get("https://www.nseindia.com/")
    time.sleep(5)

    # Wait for and type into the search input
    search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Search by Company name, Symbol or keyword... "]')))
    search_input.clear()
    search_input.send_keys(stock_name)
    time.sleep(7)

    # Click the autocomplete suggestion with "in equity"
    suggestions = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".autocompleteList")))
    for suggestion in suggestions:
        try:
            if "in equity" in suggestion.text:
                suggestion.click()
                break
        except Exception as e:
            continue
    time.sleep(5)

    # Click the 'Historical Data' tab
    historical_tab = wait.until(EC.element_to_be_clickable((By.ID, "loadHistoricalData")))
    historical_tab.click()
    time.sleep(5)

    # Wait for the historical data table to load
    table = wait.until(EC.presence_of_element_located((By.ID, "equityHistoricalTable")))

    # Extract the latest row (first row in tbody)
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    if not rows:
        print("❌ No data rows found in historical table.")
        driver.quit()
        return None

    latest_row = rows[0]
    cols = latest_row.find_elements(By.TAG_NAME, "td")
    
    # Columns 3 to 14 (index 2 to 13)
    if len(cols) < 14:
        print("❌ Not enough columns found.")
        driver.quit()
        return None

    extracted_data = [float(cols[i].text.replace(",", "")) for i in range(2, 14)]
    driver.quit()

    # Return values as a dictionary matching your form inputs
    field_names = [
        'open', 'high', 'low', 'prev_close', 'ltp', 'close',
        'vwap', 'fifty_two_w_high', 'fifty_two_w_low',
        'volume', 'value', 'no_of_trades'
    ]

    return dict(zip(field_names, extracted_data))


# If you want to run only this code to test whther running or not
# if __name__ == "__main__":
#     stock_name = input("Enter stock name to search on NSE: ").strip()
#     data = get_latest_nse_data(stock_name)
#     if data:
#         print("\n✅ Extracted Data:")
#         for key, value in data.items():
#             print(f"{key}: {value}")
#     else:
#         print("\n❌ Failed to extract data.")
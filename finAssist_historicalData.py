import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pymongo import MongoClient

# MongoDB Setup
client = MongoClient("mongodb://localhost:27017/")

def scrape_nse_historical_data():
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    driver.get("https://www.nseindia.com/market-data/live-equity-market")

    wait = WebDriverWait(driver, 20)
    time.sleep(10)  # Initial delay

    # Click on the first company name (Opens in a new tab)
    first_company = wait.until(EC.element_to_be_clickable((By.XPATH, "//table[@id='equityStockTable']//tbody/tr[2]/td[1]/a")))
    company_name = first_company.text.strip()
    first_company.click()
    time.sleep(5)

    # Switch to the new tab
    driver.switch_to.window(driver.window_handles[-1])  
    time.sleep(5)

    # Click on "Historical Data"
    try:
        historical_data_tab = wait.until(EC.element_to_be_clickable((By.ID, "loadHistoricalData")))
        driver.execute_script("arguments[0].click();", historical_data_tab)
        time.sleep(5)
    except Exception as e:
        print("Failed to click on 'Historical Data':", e)
        driver.quit()
        return

    # Click on "6M" filter
    try:
        six_months_filter = wait.until(EC.element_to_be_clickable((By.ID, "sixM")))
        six_months_filter.click()
        time.sleep(5)
    except Exception as e:
        print("Failed to click on '6M' filter:", e)
        driver.quit()
        return

    # Scrape the historical data table
    rows = driver.find_elements(By.XPATH, "//table[@id='equityHistoricalTable']//tbody/tr")
    
    # Connect to MongoDB
    db = client[company_name]
    historical_collection = db["historical_data"]

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) >= 14:
            entry = {
                "_id": cols[0].text.strip(),
                "Date": cols[0].text.strip(),
                "Series": cols[1].text.strip(),
                "OPEN": cols[2].text.strip(),
                "HIGH": cols[3].text.strip(),
                "LOW": cols[4].text.strip(),
                "PREV_CLOSE": cols[5].text.strip(),
                "LTP": cols[6].text.strip(),
                "CLOSE": cols[7].text.strip(),
                "VWAP": cols[8].text.strip(),
                "52W_H": cols[9].text.strip(),
                "52W_L": cols[10].text.strip(),
                "VOLUME": cols[11].text.strip(),
                "VALUE": cols[12].text.strip(),
                "No_of_Trades": cols[13].text.strip()
            }
            
            # Insert or update if entry exists
            historical_collection.update_one({"_id": entry["_id"]}, {"$set": entry}, upsert=True)

    print(f"Scraped and stored historical data for {company_name} in MongoDB.")

    # Click on "Trade Information" tab
    try:
        trade_info_tab = wait.until(EC.element_to_be_clickable((By.ID, "infoTrade")))
        trade_info_tab.click()
        time.sleep(7)
    except Exception as e:
        print("Failed to click on 'Trade Information':", e)
        driver.quit()
        return

    # Click on the arrow image (View All)
    try:
        view_all_arrow = wait.until(EC.presence_of_element_located((By.ID, "ann_quoteRedirect")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", view_all_arrow)
        time.sleep(7)
        view_all_arrow.click()
        time.sleep(7)
    except Exception as e:
        print("Failed to click on 'View All' arrow after scrolling:", e)
        driver.quit()
        return
    
    # Click on "6M" filter in announcements
    try:
        announcements_six_months = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@data-val='6M']")))
        announcements_six_months.click()
        time.sleep(5)
    except Exception as e:
        print("Failed to click on '6M' filter in announcements:", e)
        driver.quit()
        return

    # Scroll to load all announcement rows
    try:
        scroll_container = driver.find_element(By.ID, "corpAnnouncementTable")
        last_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
        while True:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
            time.sleep(2)
            new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
            if new_height == last_height:
                break
            last_height = new_height
    except Exception as e:
        print("Error during scrolling:", e)

    # Click all "Read More" buttons
    try:
        read_more_buttons = driver.find_elements(By.CLASS_NAME, "readMore")
        for btn in read_more_buttons:
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.1)
            except:
                continue
    except Exception as e:
        print("Failed to expand all Read More texts:", e)

    # Scrape the announcements table
    announcements_data_list = []
    announcement_rows = driver.find_elements(By.XPATH, "//div[@id='corpAnnouncementTable']//table//tbody/tr")

    for row in announcement_rows:
        cols = row.find_elements(By.TAG_NAME, "td")

        if len(cols) >= 4:
            subject = cols[0].text.strip()
            announcement_text = driver.execute_script("return arguments[0].textContent;", cols[1]).strip()
            broadcast_time = cols[3].text.strip()

            # Skip empty or duplicate-like rows
            if not subject and not announcement_text:
                continue
            if "..." in announcement_text and not cols[1].find_elements(By.CLASS_NAME, "readMore"):
                continue

            announcements_data_list.append({
                "Subject": subject,
                "Announcement": announcement_text,
                "Broadcast Date/Time": broadcast_time
            })

    # Store announcements data in MongoDB
    announcements_collection = db["announcements"]
    if announcements_data_list:
        announcements_collection.insert_many(announcements_data_list)
        print(f"Scraped and stored announcements data for {company_name} in MongoDB.")
    else:
        print(f"No announcements data found for {company_name}.")

    driver.quit()

if __name__ == "__main__":
    scrape_nse_historical_data()

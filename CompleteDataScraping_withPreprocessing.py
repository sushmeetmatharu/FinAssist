import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pymongo import MongoClient
import datetime
from dateutil import parser

# MongoDB Setup
client = MongoClient("mongodb://localhost:27017/")

def format_date_for_id(date_value):
    """Convert various date formats to YYYY-MM-DD format for _id"""
    if isinstance(date_value, str):
        try:
            # Try to parse the date string
            dt = parser.parse(date_value)
            return dt.strftime('%Y-%m-%d')
        except:
            return date_value  # Fallback to original if parsing fails
    elif isinstance(date_value, datetime.datetime):
        return date_value.strftime('%Y-%m-%d')
    return date_value

def scrape_nse_historical_data():
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    driver.get("https://www.nseindia.com/market-data/live-equity-market")

    wait = WebDriverWait(driver, 20)
    time.sleep(10)  # Let the main table load

    # Store the main tab handle
    main_tab = driver.current_window_handle

    # Loop through first 5 companies (rows 2 to 6 in the table)
    for i in range(2, 7):
        try:
            # Click on the company name (Opens in a new tab)
            company_xpath = f"//table[@id='equityStockTable']//tbody/tr[{i}]/td[1]/a"
            company_link = wait.until(EC.element_to_be_clickable((By.XPATH, company_xpath)))
            company_name = company_link.text.strip()
            print(f"\nProcessing company {i-1}: {company_name}")
            
            # Open company page in new tab
            company_link.click()
            time.sleep(5)

            # Switch to the new tab
            new_tab = [tab for tab in driver.window_handles if tab != main_tab][0]
            driver.switch_to.window(new_tab)
            time.sleep(5)

            # Click on "Historical Data"
            try:
                historical_data_tab = wait.until(EC.element_to_be_clickable((By.ID, "loadHistoricalData")))
                driver.execute_script("arguments[0].click();", historical_data_tab)
                time.sleep(5)
            except Exception as e:
                print("Failed to click on 'Historical Data':", e)
                driver.close()
                driver.switch_to.window(main_tab)
                continue
            
            # Click on "6M" filter
            try:
                six_months_filter = wait.until(EC.element_to_be_clickable((By.ID, "sixM")))
                six_months_filter.click()
                time.sleep(3)

                # Click on "Filter" button after selecting 6M
                filter_button = wait.until(EC.element_to_be_clickable((By.ID, "tradeDataFilter")))
                filter_button.click()
                time.sleep(5)
            except Exception as e:
                print("Failed to click on '6M' filter or 'Filter' button:", e)
                driver.close()
                driver.switch_to.window(main_tab)
                continue

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

                # Scrape the Trade Information table
                try:
                    scraped_at = datetime.datetime.now()
                    trade_info_data = {
                        "_id": format_date_for_id(scraped_at),
                        "Traded Volume (Lakhs)": driver.find_element(By.ID, "orderBookTradeVol").text.strip(),
                        "Traded Value (₹ Cr.)": driver.find_element(By.ID, "orderBookTradeVal").text.strip(),
                        "Total Market Cap (₹ Cr.)": driver.find_element(By.ID, "orderBookTradeTMC").text.strip(),
                        "Free Float Market Cap (₹ Cr.)": driver.find_element(By.ID, "orderBookTradeFFMC").text.strip(),
                        "Impact Cost": driver.find_element(By.ID, "orderBookTradeIC").text.strip(),
                        "% of Deliverable / Traded Quantity": driver.find_element(By.ID, "orderBookDeliveryTradedQty").text.strip(),
                        "Applicable Margin Rate": driver.find_element(By.ID, "orderBookAppMarRate").text.strip(),
                        "Face Value": driver.find_element(By.ID, "mainFaceValue").text.strip(),
                        "Scraped_At": scraped_at
                    }

                    trade_info_collection = db["trade_information"]
                    trade_info_collection.update_one(
                        {"_id": trade_info_data["_id"]},
                        {"$set": trade_info_data},
                        upsert=True
                    )

                    print(f"Scraped and stored trade information for {company_name} in MongoDB.")
                except Exception as e:
                    print("Failed to scrape Trade Information table:", e)

                # Scrape the Price Information table
                try:
                    time.sleep(3)
                    scraped_at = datetime.datetime.now()
                    price_info_data = {
                        "_id": format_date_for_id(scraped_at),
                        "52 Week High": driver.find_element(By.ID, "week52highVal").text.strip(),
                        "52 Week High Date": driver.find_element(By.ID, "week52HighDate").text.strip(),
                        "52 Week Low": driver.find_element(By.ID, "week52lowVal").text.strip(),
                        "52 Week Low Date": driver.find_element(By.ID, "week52LowDate").text.strip(),
                        "Upper Band": driver.find_element(By.ID, "upperbandVal").text.strip(),
                        "Lower Band": driver.find_element(By.ID, "lowerbandVal").text.strip(),
                        "Price Band (%)": driver.find_element(By.ID, "pricebandVal").text.strip(),
                        "Daily Volatility": driver.find_element(By.ID, "orderBookTradeDV").text.strip(),
                        "Annualised Volatility": driver.find_element(By.ID, "orderBookTradeAV").text.strip(),
                        "Tick Size": driver.find_element(By.ID, "tickSize").text.strip(),
                        "Scraped_At": scraped_at
                    }

                    price_info_collection = db["price_information"]
                    price_info_collection.update_one(
                        {"_id": price_info_data["_id"]},
                        {"$set": price_info_data},
                        upsert=True
                    )

                    print(f"Scraped and stored price information for {company_name} in MongoDB.")
                except Exception as e:
                    print("Failed to scrape Price Information table:", e)

                # Scrape the Securities Information table
                try:
                    time.sleep(3)
                    scraped_at = datetime.datetime.now()
                    securities_info_data = {
                        "_id": format_date_for_id(scraped_at),
                        "Status": driver.find_element(By.ID, "Listed").text.strip(),
                        "Trading Status": driver.find_element(By.ID, "Active").text.strip(),
                        "Date of Listing": driver.find_element(By.XPATH, "//td[@id='Date_of_Listing']/following-sibling::td").text.strip(),
                        "Adjusted P/E": driver.find_element(By.XPATH, "//td[@id='SectoralIndxPE']/following-sibling::td").text.strip(),
                        "Symbol P/E": driver.find_element(By.XPATH, "//td[@id='Symbol_PE']/following-sibling::td").text.strip(),
                        "Index": driver.find_element(By.XPATH, "//td[@id='Sectoral_Index']/following-sibling::td").text.strip(),
                        "Basic Industry": driver.find_element(By.XPATH, "//span[@id='BasicIndustry']/ancestor::td/following-sibling::td").text.strip(),
                        "Scraped_At": scraped_at
                    }

                    securities_info_collection = db["securities_information"]
                    securities_info_collection.update_one(
                        {"_id": securities_info_data["_id"]},
                        {"$set": securities_info_data},
                        upsert=True
                    )

                    print(f"Scraped and stored securities information for {company_name} in MongoDB.")
                except Exception as e:
                    print("Failed to scrape Securities Information table:", e)
            
            except Exception as e:
                print("Failed to click on 'Trade Information':", e)
                driver.close()
                driver.switch_to.window(main_tab)
                continue

            # Click on the arrow image (View All)
            try:
                view_all_arrow = wait.until(EC.presence_of_element_located((By.ID, "ann_quoteRedirect")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", view_all_arrow)
                time.sleep(7)
                view_all_arrow.click()
                time.sleep(7)
            except Exception as e:
                print("Failed to click on 'View All' arrow after scrolling:", e)
                driver.close()
                driver.switch_to.window(main_tab)
                continue
            
            # Click on "6M" filter in announcements
            try:
                announcements_six_months = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@data-val='6M']")))
                announcements_six_months.click()
                time.sleep(5)
            except Exception as e:
                print("Failed to click on '6M' filter in announcements:", e)
                driver.close()
                driver.switch_to.window(main_tab)
                continue

            try:
                scroll_container = driver.find_element(By.ID, "corpAnnouncementTable")
                max_attempts = 15  # Safety cap to avoid infinite scroll
                prev_row_count = 0

                for attempt in range(max_attempts):
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                    time.sleep(2)

                    rows_loaded = driver.find_elements(By.XPATH, "//div[@id='corpAnnouncementTable']//table//tbody/tr")
                    current_row_count = len(rows_loaded)
                    print(f"Scroll attempt {attempt+1}: {current_row_count} rows loaded")

                    if current_row_count >= 50:
                        break  # Desired row count reached
                    if current_row_count == prev_row_count:
                        break  # No new rows loaded, stop scrolling
                    prev_row_count = current_row_count
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

                    # Format the broadcast date as YYYY-MM-DD for _id
                    try:
                        broadcast_date = parser.parse(broadcast_time.split()[0], dayfirst=True)
                        broadcast_id = broadcast_date.strftime('%Y-%m-%d')
                    except:
                        broadcast_id = broadcast_time  # Fallback to original if parsing fails

                    announcements_data_list.append({
                        "_id": broadcast_id,
                        "Subject": subject,
                        "Announcement": announcement_text,
                        "Broadcast Date/Time": broadcast_time
                    })

            # Store announcements data in MongoDB
            announcements_collection = db["announcements"]
            if announcements_data_list:
                # Using bulk_write with update_one operations for upsert functionality
                from pymongo import UpdateOne
                operations = [
                    UpdateOne(
                        {"_id": doc["_id"]},
                        {"$set": doc},
                        upsert=True
                    )
                    for doc in announcements_data_list
                ]
                if operations:
                    announcements_collection.bulk_write(operations)
                print(f"Scraped and stored announcements data for {company_name} in MongoDB.")
            else:
                print(f"No announcements data found for {company_name}.")

            # Close the current tab and switch back to main tab
            driver.close()
            driver.switch_to.window(main_tab)
            time.sleep(3)

        except Exception as e:
            print(f"Error processing company {i-1}:", str(e))
            # Make sure we're back on the main tab for next iteration
            if main_tab in driver.window_handles:
                driver.switch_to.window(main_tab)
            continue

    # Close the browser when done with all companies
    driver.quit()
    print("\nCompleted scraping for all 5 companies.")

if __name__ == "__main__":
    scrape_nse_historical_data()

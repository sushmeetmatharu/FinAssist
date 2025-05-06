import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pymongo import MongoClient
import datetime
from dateutil import parser
from pymongo import UpdateOne
import os
import shutil

# MongoDB Setup
client = MongoClient("mongodb://localhost:27017/")

# Configuration for download directory
DOWNLOAD_DIR = "D:\\Downloads\\NSE_Data"

def ensure_download_directory(company_name):
    """Create company-specific directory if it doesn't exist"""
    company_dir = os.path.join(DOWNLOAD_DIR, company_name)
    os.makedirs(company_dir, exist_ok=True)
    return company_dir

def wait_for_download_complete(download_dir, timeout=60, check_interval=1):
    """Wait for all downloads to complete in the specified directory"""
    end_time = time.time() + timeout
    while time.time() < end_time:
        time.sleep(check_interval)
        # Check if any .crdownload files exist
        if not any(fname.endswith('.crdownload') for fname in os.listdir(download_dir)):
            # Check if any .csv files exist
            csv_files = [f for f in os.listdir(download_dir) if f.endswith('.csv')]
            if csv_files:
                return csv_files
    return []

def rename_and_move_files(company_dir, company_name):
    """Rename and organize downloaded files into proper structure"""
    downloaded_files = os.listdir(DOWNLOAD_DIR)
    moved_files = []
    
    for filename in downloaded_files:
        src_path = os.path.join(DOWNLOAD_DIR, filename)
        
        if filename.startswith('Quote-Equity-') and filename.endswith('.csv'):
            # Historical data file
            new_name = f"{company_name}_historical_data.csv"
            dest_path = os.path.join(company_dir, new_name)
            shutil.move(src_path, dest_path)
            moved_files.append(dest_path)
            
        elif filename.startswith('CF-AN-equities-') and filename.endswith('.csv'):
            # Announcements file
            new_name = f"{company_name}_announcements_data.csv"
            dest_path = os.path.join(company_dir, new_name)
            shutil.move(src_path, dest_path)
            moved_files.append(dest_path)
    
    return moved_files

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

def clean_announcement_text(text):
    """Clean up announcement text by removing 'Read Less' and ensuring proper punctuation"""
    # Remove "Read Less" if it exists at the end
    if text.endswith("Read Less"):
        text = text[:-9].strip()
    
    # Ensure the text ends with proper punctuation
    if text and not text[-1] in {'.', '!', '?'}:
        text = text + '.'
    
    return text

def clean_numeric_value(value):
    """Remove commas and other non-numeric characters from a string (except decimal point)"""
    if isinstance(value, str):
        # Remove commas, currency symbols, and any other non-numeric characters (except .)
        cleaned = ''.join(c for c in value if c.isdigit() or c == '.')
        return cleaned if cleaned else value  # Return original if cleaning results in empty string
    return value

def scrape_nse_historical_data():
    options = uc.ChromeOptions()
    
    # Set default download directory
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
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
            
            # Create company-specific directory
            company_dir = ensure_download_directory(company_name)
            
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
            
            # Click on "1Y" filter
            try:
                one_year_filter = wait.until(EC.element_to_be_clickable((By.ID, "oneY")))
                one_year_filter.click()
                time.sleep(3)

                # Click on "Filter" button after selecting 1Y
                filter_button = wait.until(EC.element_to_be_clickable((By.ID, "tradeDataFilter")))
                filter_button.click()
                time.sleep(5)
            except Exception as e:
                print("Failed to click on '1Y' filter or 'Filter' button:", e)
                driver.close()
                driver.switch_to.window(main_tab)
                continue

            # Click on Download (.csv) button for historical data
            try:
                download_button = wait.until(EC.element_to_be_clickable((By.ID, "tradeDataDownload")))
                download_button.click()
                time.sleep(5)
                
                # Wait for download to complete and rename/move files
                downloaded_files = wait_for_download_complete(DOWNLOAD_DIR)
                moved_files = rename_and_move_files(company_dir, company_name)
                
                if moved_files:
                    print(f"Successfully downloaded and organized files for {company_name}:")
                    for f in moved_files:
                        print(f" - {os.path.basename(f)}")
                else:
                    print(f"Failed to verify download for {company_name}")
            except Exception as e:
                print("Failed to download historical data CSV:", e)

            # Scrape the historical data table (original MongoDB storage)
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
                        "OPEN": clean_numeric_value(cols[2].text.strip()),
                        "HIGH": clean_numeric_value(cols[3].text.strip()),
                        "LOW": clean_numeric_value(cols[4].text.strip()),
                        "PREV_CLOSE": clean_numeric_value(cols[5].text.strip()),
                        "LTP": clean_numeric_value(cols[6].text.strip()),
                        "CLOSE": clean_numeric_value(cols[7].text.strip()),
                        "VWAP": clean_numeric_value(cols[8].text.strip()),
                        "52W_H": clean_numeric_value(cols[9].text.strip()),
                        "52W_L": clean_numeric_value(cols[10].text.strip()),
                        "VOLUME": clean_numeric_value(cols[11].text.strip()),
                        "VALUE": clean_numeric_value(cols[12].text.strip()),
                        "No_of_Trades": clean_numeric_value(cols[13].text.strip())
                    }
                    
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
                        "Traded Volume (Lakhs)": clean_numeric_value(driver.find_element(By.ID, "orderBookTradeVol").text.strip()),
                        "Traded Value (₹ Cr)": clean_numeric_value(driver.find_element(By.ID, "orderBookTradeVal").text.strip()),
                        "Total Market Cap (₹ Cr)": clean_numeric_value(driver.find_element(By.ID, "orderBookTradeTMC").text.strip()),
                        "Free Float Market Cap (₹ Cr)": clean_numeric_value(driver.find_element(By.ID, "orderBookTradeFFMC").text.strip()),
                        "Impact Cost": clean_numeric_value(driver.find_element(By.ID, "orderBookTradeIC").text.strip()),
                        "% of Deliverable / Traded Quantity": clean_numeric_value(driver.find_element(By.ID, "orderBookDeliveryTradedQty").text.strip()),
                        "Applicable Margin Rate": clean_numeric_value(driver.find_element(By.ID, "orderBookAppMarRate").text.strip()),
                        "Face Value": clean_numeric_value(driver.find_element(By.ID, "mainFaceValue").text.strip()),
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
                        "52 Week High": clean_numeric_value(driver.find_element(By.ID, "week52highVal").text.strip()),
                        "52 Week High Date": driver.find_element(By.ID, "week52HighDate").text.strip(),
                        "52 Week Low": clean_numeric_value(driver.find_element(By.ID, "week52lowVal").text.strip()),
                        "52 Week Low Date": driver.find_element(By.ID, "week52LowDate").text.strip(),
                        "Upper Band": clean_numeric_value(driver.find_element(By.ID, "upperbandVal").text.strip()),
                        "Lower Band": clean_numeric_value(driver.find_element(By.ID, "lowerbandVal").text.strip()),
                        "Price Band (%)": clean_numeric_value(driver.find_element(By.ID, "pricebandVal").text.strip()),
                        "Daily Volatility": clean_numeric_value(driver.find_element(By.ID, "orderBookTradeDV").text.strip()),
                        "Annualised Volatility": clean_numeric_value(driver.find_element(By.ID, "orderBookTradeAV").text.strip()),
                        "Tick Size": clean_numeric_value(driver.find_element(By.ID, "tickSize").text.strip()),
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
            
            # Click on "1Y" filter and View all button for announcements which opens a new tab
            try:
                announcements_one_year = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@data-val='1Y']")))
                announcements_one_year.click()
                time.sleep(5)
                announcements_view_all = wait.until(EC.element_to_be_clickable((By.ID, "corp-annc-link")))
                announcements_view_all.click()
                time.sleep(5)
            except Exception as e:
                print("Failed to click on '1Y' filter in announcements:", e)
                driver.close()
                driver.switch_to.window(new_tab)
                continue

            # Switch to the new announcements tab
            announcements_tab = [tab for tab in driver.window_handles if tab not in [main_tab, new_tab]][0]
            driver.switch_to.window(announcements_tab)
            time.sleep(5)
            announcements_one_year = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@data-val='1Y']")))
            announcements_one_year.click()
            time.sleep(5)

            # Click on Download (.csv) button for announcements
            try:
                download_button = wait.until(EC.element_to_be_clickable((By.ID, "CFanncEquity-download")))
                download_button.click()
                time.sleep(5)
                
                # Wait for download to complete and rename/move files
                downloaded_files = wait_for_download_complete(DOWNLOAD_DIR)
                moved_files = rename_and_move_files(company_dir, company_name)
                
                if moved_files:
                    print(f"Successfully downloaded and organized files for {company_name}:")
                    for f in moved_files:
                        print(f" - {os.path.basename(f)}")
                else:
                    print(f"Failed to verify download for {company_name}")
            except Exception as e:
                print("Failed to download announcements CSV:", e)

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
            try:
                announcement_rows = driver.find_elements(By.XPATH, "//div[@id='CFanncEquityTable']//table//tbody/tr")
                
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

                        # Clean up the announcement text
                        announcement_text = clean_announcement_text(announcement_text)

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
            except Exception as e:
                print(f"Failed to scrape announcements table for {company_name}:", e)

            # Store announcements data in MongoDB
            announcements_collection = db["announcements"]
            if announcements_data_list:
                # Using bulk_write with update_one operations for upsert functionality
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

            # Close the announcements tab and switch back to company tab
            driver.close()
            driver.switch_to.window(new_tab)
            
            # Close the company tab and switch back to main tab
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

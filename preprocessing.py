from pymongo import MongoClient
from datetime import datetime

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")

# List all databases (i.e., company names)
company_dbs = client.list_database_names()

for db_name in company_dbs:
    db = client[db_name]

    # 1. Preprocess announcements
    if "announcements" in db.list_collection_names():
        announcements = db["announcements"]
        all_docs = list(announcements.find())

        for doc in all_docs:
            new_announcement = doc.get("Announcement", "").replace("Read Less", "").strip()
            if not new_announcement.endswith("."):
                new_announcement += "."

            # Parse and format new _id
            try:
                bdt = doc.get("Broadcast Date/Time", "")
                dt_obj = datetime.strptime(bdt.split()[0], "%d-%b-%Y")
                new_id = dt_obj.strftime("%Y-%m-%d")
            except Exception as e:
                print(f"Error parsing Broadcast Date for {doc.get('_id')}: {e}")
                continue

            # Update with new _id
            new_doc = doc.copy()
            new_doc["_id"] = new_id
            new_doc["Announcement"] = new_announcement

            try:
                announcements.delete_one({"_id": doc["_id"]})
                announcements.insert_one(new_doc)
            except Exception as e:
                print(f"Error updating announcements doc for {db_name}: {e}")

    # 2. Preprocess trade_information, price_information, securities_information
    for collection_name in ["trade_information", "price_information", "securities_information"]:
        if collection_name in db.list_collection_names():
            coll = db[collection_name]
            all_docs = list(coll.find())

            for doc in all_docs:
                scraped_at = doc.get("Scraped_At")
                if isinstance(scraped_at, datetime):
                    date_id = scraped_at.strftime("%Y-%m-%d")
                else:
                    continue  # Skip if Scraped_At is missing or invalid

                new_doc = doc.copy()
                new_doc["_id"] = date_id

                try:
                    coll.delete_one({"_id": doc["_id"]})
                    coll.insert_one(new_doc)
                except Exception as e:
                    print(f"Error updating {collection_name} doc for {db_name}: {e}")

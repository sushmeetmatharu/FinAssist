import os
import pandas as pd
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import numpy as np
import matplotlib.pyplot as plt

# Path to your folder
BASE_DIR = r"D:\Downloads\NSE_Data"

def parse_announcement_date(date_str):
    # Replace multiple spaces with a single space and strip leading/trailing whitespace
    date_str = ' '.join(date_str.strip().split())
    return datetime.strptime(date_str, "%d-%b-%Y %H:%M:%S").date()

def parse_historical_date(date_str):
    date_str = ' '.join(date_str.strip().split())  # Normalize spacing
    return datetime.strptime(date_str, "%d-%b-%Y").date()

def calculate_percentage_change(prev_close, next_close):
    return round(((next_close - prev_close) / prev_close) * 100, 2)

def extract_features_and_labels(announcements_df, historical_df):
    announcements_df['BROADCAST_DATE'] = announcements_df['BROADCAST DATE/TIME'].apply(parse_announcement_date)
    historical_df['DATE'] = historical_df['Date'].apply(parse_historical_date)
    # Convert 'close' to numeric
    historical_df['close'] = pd.to_numeric(historical_df['close'], errors='coerce')

    label_data = []

    for _, row in announcements_df.iterrows():
        ann_date = row['BROADCAST_DATE']
        next_day = ann_date + timedelta(days=1)
        prev_day = ann_date - timedelta(days=1)

        prev_day_row = historical_df[historical_df['DATE'] == prev_day]
        next_day_row = historical_df[historical_df['DATE'] == next_day]

        if not prev_day_row.empty and not next_day_row.empty:
            prev_close = prev_day_row['close'].values[0]
            next_close = next_day_row['close'].values[0]
            if pd.notna(prev_close) and pd.notna(next_close) and prev_close != 0:
                percent_change = calculate_percentage_change(prev_close, next_close)
                label_data.append({
                    "text": f"{row['SUBJECT']}. {row['DETAILS']}",
                    "percentage_change": percent_change
                })

    return pd.DataFrame(label_data)

# Step 1: Merge data from all companies
all_data = []

for company_folder in os.listdir(BASE_DIR):
    company_path = os.path.join(BASE_DIR, company_folder)
    if os.path.isdir(company_path):
        files = os.listdir(company_path)
        announcements_file = [f for f in files if 'announcements' in f.lower()][0]
        historical_file = [f for f in files if 'historical' in f.lower()][0]

        announcements_path = os.path.join(company_path, announcements_file)
        historical_path = os.path.join(company_path, historical_file)

        announcements_df = pd.read_csv(announcements_path)
        announcements_df.columns = announcements_df.columns.str.strip()
        historical_df = pd.read_csv(historical_path)
        historical_df.columns = historical_df.columns.str.strip()  # Remove trailing spaces

        features_labels = extract_features_and_labels(announcements_df, historical_df)
        all_data.append(features_labels)

# Combine all into one DataFrame
dataset = pd.concat(all_data, ignore_index=True)

# Step 2: Text Vectorization
vectorizer = TfidfVectorizer(max_features=500)
X = vectorizer.fit_transform(dataset['text']).toarray()
y = dataset['percentage_change'].values

# Step 3: Train/Test split and Model Training
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Step 4: Evaluation
y_pred = model.predict(X_test)
print("R2 Score:", r2_score(y_test, y_pred))
print("RMSE:", mean_squared_error(y_test, y_pred, squared=False))

# Calculate errors
errors = y_test - y_pred

# 1. Histogram of Prediction Errors
plt.figure(figsize=(8, 5))
plt.hist(errors, bins=30, color='skyblue', edgecolor='black')
plt.title("Histogram of Prediction Errors")
plt.xlabel("Prediction Error (Actual - Predicted)")
plt.ylabel("Frequency")
plt.grid(True)
plt.show()

# 2. Actual vs. Predicted Scatter Plot
plt.figure(figsize=(8, 5))
plt.scatter(y_test, y_pred, alpha=0.7, color='mediumseagreen')
plt.plot([min(y_test), max(y_test)], [min(y_test), max(y_test)], 'r--')  # reference line
plt.title("Actual vs. Predicted Percentage Change")
plt.xlabel("Actual Percentage Change")
plt.ylabel("Predicted Percentage Change")
plt.grid(True)
plt.show()

# Step 5: Save model and vectorizer
joblib.dump(model, "stock_price_change_model.pkl")
joblib.dump(vectorizer, "announcement_vectorizer.pkl")

# Step 6: Prediction Function
def predict_announcement_effect(announcement_text):
    vectorizer = joblib.load("announcement_vectorizer.pkl")
    model = joblib.load("stock_price_change_model.pkl")
    vect_text = vectorizer.transform([announcement_text]).toarray()
    predicted_change = model.predict(vect_text)[0]
    direction = "increase" if predicted_change > 0 else "decrease"
    return direction, round(abs(predicted_change), 2)

# Example usage
example_announcement = "Board Meeting Intimation for Quarterly Results"
direction, percentage = predict_announcement_effect(example_announcement)
print(f"The stock is likely to {direction} by {percentage}%")

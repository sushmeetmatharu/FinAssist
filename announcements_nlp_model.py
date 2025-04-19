import pandas as pd
import numpy as np
from pymongo import MongoClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import classification_report, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler
from textblob import TextBlob
import re
from datetime import datetime, timedelta
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# Download NLTK resources
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('punkt')

# MongoDB connection setup
def get_mongo_client(uri="mongodb://localhost:27017/"):
    return MongoClient(uri)

# Text preprocessing
def preprocess_text(text):
    if not isinstance(text, str):
        return ""
    
    # Lowercase
    text = text.lower()
    # Remove special chars
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    # Tokenize
    tokens = nltk.word_tokenize(text)
    # Remove stopwords
    stop_words = set(stopwords.words('english'))
    tokens = [word for word in tokens if word not in stop_words]
    # Lemmatize
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(word) for word in tokens]
    
    return ' '.join(tokens)

# Feature extraction from announcements
def extract_announcement_features(announcement_text, subject):
    processed_text = preprocess_text(announcement_text)
    processed_subject = preprocess_text(subject)
    
    # TextBlob sentiment analysis
    blob = TextBlob(announcement_text)
    sentiment_polarity = blob.sentiment.polarity
    sentiment_subjectivity = blob.sentiment.subjectivity
    
    # Length features
    text_length = len(announcement_text)
    word_count = len(announcement_text.split())
    
    # Subject features
    subject_length = len(subject)
    subject_word_count = len(subject.split())
    
    # Keyword features
    keywords = ['dividend', 'meeting', 'acquisition', 'merger', 'results', 'financial', 'board', 
                'approval', 'issue', 'subsidiary', 'share', 'price', 'rating', 'loan', 'debt']
    keyword_counts = {f'kw_{kw}': announcement_text.lower().count(kw) for kw in keywords}
    
    return {
        'processed_text': processed_text,
        'processed_subject': processed_subject,
        'sentiment_polarity': sentiment_polarity,
        'sentiment_subjectivity': sentiment_subjectivity,
        'text_length': text_length,
        'word_count': word_count,
        'subject_length': subject_length,
        'subject_word_count': subject_word_count,
        **keyword_counts
    }

# Get price movement after announcement
def get_price_movement(company_db, announcement_date, lookahead_days=3):
    hist_data = company_db['historical_data']
    
    # Convert announcement_date to datetime if it's string
    if isinstance(announcement_date, str):
        announcement_date = datetime.strptime(announcement_date, "%Y-%m-%d")
    
    # Get announcement day price
    announcement_day = hist_data.find_one({"Date": announcement_date.strftime("%d-%b-%Y")})
    if not announcement_day:
        return None
    
    # Get future price (lookahead_days after announcement)
    future_date = announcement_date + timedelta(days=lookahead_days)
    future_day = hist_data.find_one({"Date": future_date.strftime("%d-%b-%Y")})
    
    if not future_day:
        # Try to find the next available trading day
        for i in range(1, 7):
            future_date = announcement_date + timedelta(days=lookahead_days + i)
            future_day = hist_data.find_one({"Date": future_date.strftime("%d-%b-%Y")})
            if future_day:
                break
    
    if not future_day:
        return None
    
    # Calculate percentage change
    try:
        announcement_close = float(announcement_day['CLOSE'])
        future_close = float(future_day['CLOSE'])
        pct_change = (future_close - announcement_close) / announcement_close * 100
        return pct_change
    except (KeyError, TypeError):
        return None

# Prepare dataset from MongoDB
def prepare_dataset(company_db, max_samples=None):
    announcements = company_db['announcements']
    dataset = []
    
    # Get all announcements with their dates
    for i, ann in enumerate(announcements.find()):
        if max_samples and i >= max_samples:
            break
            
        try:
            # Extract announcement features
            features = extract_announcement_features(
                ann.get('Announcement', ''),
                ann.get('Subject', '')
            )
            
            # Get price movement
            pct_change = get_price_movement(company_db, ann['_id'])
            if pct_change is None:
                continue
                
            # Add to dataset
            dataset.append({
                **features,
                'pct_change': pct_change,
                'direction': 1 if pct_change > 0 else 0,  # 1 for increase, 0 for decrease
                'announcement_date': ann['_id'],
                'raw_announcement': ann.get('Announcement', ''),
                'raw_subject': ann.get('Subject', '')
            })
        except Exception as e:
            print(f"Error processing announcement {ann['_id']}: {str(e)}")
            continue
    
    return pd.DataFrame(dataset)

# Model training
def train_models(df):
    # Split data
    X = df.drop(['pct_change', 'direction', 'announcement_date', 'raw_announcement', 'raw_subject'], axis=1)
    y_direction = df['direction']
    y_pct_change = df['pct_change']
    
    X_train, X_test, y_dir_train, y_dir_test = train_test_split(
        X, y_direction, test_size=0.2, random_state=42
    )
    
    _, _, y_pct_train, y_pct_test = train_test_split(
        X, y_pct_change, test_size=0.2, random_state=42
    )
    
    # Define preprocessing
    text_features = ['processed_text', 'processed_subject']
    numeric_features = [col for col in X.columns if col not in text_features]
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('text', TfidfVectorizer(max_features=1000), 'processed_text'),
            ('subject', TfidfVectorizer(max_features=200), 'processed_subject'),
            ('num', StandardScaler(), numeric_features)
        ])
    
    # Direction classifier
    dir_clf = Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
    ])
    
    # Percentage change regressor
    pct_reg = Pipeline([
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
    ])
    
    # Train models
    dir_clf.fit(X_train, y_dir_train)
    pct_reg.fit(X_train, y_pct_train)
    
    # Evaluate
    dir_pred = dir_clf.predict(X_test)
    pct_pred = pct_reg.predict(X_test)
    
    print("Direction Classification Report:")
    print(classification_report(y_dir_test, dir_pred))
    
    print("\nPercentage Change Regression Metrics:")
    print(f"MSE: {mean_squared_error(y_pct_test, pct_pred)}")
    print(f"RMSE: {np.sqrt(mean_squared_error(y_pct_test, pct_pred))}")
    
    return dir_clf, pct_reg

# Prediction function
def predict_announcement_impact(model_dir, model_pct, announcement_text, subject):
    # Extract features
    features = extract_announcement_features(announcement_text, subject)
    
    # Create DataFrame with same structure as training data
    input_data = pd.DataFrame([{
        'processed_text': features['processed_text'],
        'processed_subject': features['processed_subject'],
        'sentiment_polarity': features['sentiment_polarity'],
        'sentiment_subjectivity': features['sentiment_subjectivity'],
        'text_length': features['text_length'],
        'word_count': features['word_count'],
        'subject_length': features['subject_length'],
        'subject_word_count': features['subject_word_count'],
        **{f'kw_{kw}': features.get(f'kw_{kw}', 0) for kw in [
            'dividend', 'meeting', 'acquisition', 'merger', 'results', 'financial', 'board',
            'approval', 'issue', 'subsidiary', 'share', 'price', 'rating', 'loan', 'debt'
        ]}
    }])
    
    # Make predictions
    direction = model_dir.predict(input_data)[0]
    pct_change = model_pct.predict(input_data)[0]
    
    return {
        'direction': 'increase' if direction == 1 else 'decrease',
        'percentage_change': pct_change,
        'confidence': max(model_dir.predict_proba(input_data)[0])  # Confidence score
    }

# Main execution
if __name__ == "__main__":
    # Connect to MongoDB
    client = get_mongo_client()
    company_db = client['BAJAJFINSV']  # Replace with your company database name
    
    # Prepare dataset
    print("Preparing dataset...")
    df = prepare_dataset(company_db, max_samples=1000)  # Limit samples for demo
    
    if len(df) == 0:
        print("No valid data found. Check your MongoDB collections.")
        exit()
    
    print(f"Dataset prepared with {len(df)} samples")
    
    # Train models
    print("Training models...")
    dir_clf, pct_reg = train_models(df)
    
    # Example prediction
    test_announcement = "Bajaj Finserv has informed the Exchange regarding Notice of Annual General Meeting and e-Voting information."
    test_subject = "Shareholders meeting"
    
    prediction = predict_announcement_impact(dir_clf, pct_reg, test_announcement, test_subject)
    
    print("\nExample Prediction:")
    print(f"Announcement: {test_announcement}")
    print(f"Subject: {test_subject}")
    print(f"Predicted movement: {prediction['direction']} by {prediction['percentage_change']:.2f}%")
    print(f"Confidence: {prediction['confidence']:.2f}")
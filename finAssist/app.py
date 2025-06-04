from flask import Flask, render_template, request
import pickle
import joblib
import numpy as np
import tensorflow as tf
from auto_fill_nse import get_latest_nse_data
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Load announcement model (ready)
model_bundle = joblib.load(r"D:\Downloads\finAssist_webpage\announcements_nlp_model.pkl")
announcement_model = model_bundle["model"]
vectorizer = model_bundle["vectorizer"]

# Load the Keras model for price prediction
price_model = tf.keras.models.load_model(r"D:\Downloads\finAssist_webpage\TATASTEEL_model (1).h5")

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/predict_news", methods=["GET", "POST"])
def predict_news():
    prediction = None
    recommendation = None
    stock_name = ""
    percentage_change = None
    auto_data = {}

    if request.method == "POST":
        stock_name = request.form.get("stock_name")
        announcement = request.form.get("announcement")

        if announcement:
            X = vectorizer.transform([announcement])
            percentage_change = announcement_model.predict(X)[0]
            if percentage_change > 0:
                prediction = f"The stock is likely to increase by {percentage_change:.2f}%."
            else:
                prediction = f"The stock is likely to decrease by {abs(percentage_change):.2f}%."

            if percentage_change >= 1.5:
                recommendation = f"Recommendation: Invest in {stock_name.upper()} – An upside can be foreseen."
            else:
                recommendation = f"Recommendation: Avoid investing in {stock_name.upper()} now."

    return render_template("predict_news.html", prediction=prediction, recommendation=recommendation,
                           stock_name=stock_name, percentage_change=percentage_change,
                           auto_data=auto_data)

@app.route("/predict_price", methods=["GET", "POST"])
def predict_price():
    closing_price = None
    stock_name = ""
    auto_data = {}

    if request.method == "POST":
        stock_name = request.form.get("stock_name")

        if stock_name:
            auto_data = get_latest_nse_data(stock_name)

        try:
            features = [
                float(request.form['open']),
                float(request.form['high']),
                float(request.form['low']),
                float(request.form['prev_close']),
                float(request.form['ltp']),
                float(request.form['close']),
                float(request.form['vwap']),
                float(request.form['fifty_two_w_high']),
                float(request.form['fifty_two_w_low']),
                float(request.form['volume']),
                float(request.form['value']),
                float(request.form['no_of_trades']),
            ]
            input_array = np.array([features])
            pred = price_model.predict(input_array)
            closing_price = round(pred[0][0], 2)
        except Exception as e:
            closing_price = f"Error: {e}"

    return render_template("predict_price.html", closing_price=closing_price,
                           stock_name=stock_name, auto_data=auto_data)

@app.route("/news")
def show_news():
    url = "https://economictimes.indiatimes.com/markets/stocks/news"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        stories = soup.find_all("div", class_="eachStory")
        headlines = []
        for story in stories[:5]:
            headline = story.find("a")
            if headline:
                headlines.append({
                    "title": headline.get_text(strip=True),
                    "link": "https://economictimes.indiatimes.com" + headline['href']
                })

    except Exception as e:
        headlines = [{"title": f"Error fetching news: {e}", "link": "#"}]

    return render_template("news.html", headlines=headlines)

@app.route("/chatbot", methods=["GET"])
def chatbot():
    return render_template("chatbot.html")

if __name__ == "__main__":
    app.run(debug=True)

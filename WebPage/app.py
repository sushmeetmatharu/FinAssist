from flask import Flask, render_template, request
import pickle
import joblib
import numpy as np
import tensorflow as tf
from auto_fill_nse import get_latest_nse_data

app = Flask(__name__)

# Load announcement model (ready)
model_bundle = joblib.load(r"D:\Downloads\finAssist_webpage\announcements_nlp_model.pkl")

announcement_model = model_bundle["model"]
vectorizer = model_bundle["vectorizer"]

# Load the Keras model
price_model = tf.keras.models.load_model(r"D:\Downloads\finAssist_webpage\TATASTEEL_model (1).h5")


# @app.route("/", methods=["GET", "POST"])
# def index():
#     prediction = None
#     recommendation = None
#     stock_name = ""
#     percentage_change = None
#     closing_price = None

#     if request.method == "POST":
#         if 'announcement' in request.form:
#             stock_name = request.form.get("stock_name")
#             announcement = request.form.get("announcement")

#             if announcement:
#                 X = vectorizer.transform([announcement])
#                 percentage_change = announcement_model.predict(X)[0]
#                 if percentage_change > 0:
#                     prediction = f"The stock is likely to increase by {percentage_change:.2f}%."
#                 else:
#                     prediction = f"The stock is likely to decrease by {abs(percentage_change):.2f}%."

#                 if percentage_change >= 1.5:
#                     recommendation = f"Recommendation: Invest in {stock_name.upper()} – An upside can be foreseen."
#                 else:
#                     recommendation = f"Recommendation: Avoid investing in {stock_name.upper()} now."

#         elif 'predict_price' in request.form:
#             try:
#                 features = [
#                     float(request.form['open']),
#                     float(request.form['high']),
#                     float(request.form['low']),
#                     float(request.form['prev_close']),
#                     float(request.form['ltp']),
#                     float(request.form['close']),
#                     float(request.form['vwap']),
#                     float(request.form['fifty_two_w_high']),
#                     float(request.form['fifty_two_w_low']),
#                     float(request.form['volume']),
#                     float(request.form['value']),
#                     float(request.form['no_of_trades']),
#                 ]
#                 input_array = np.array([features])
#                 pred = price_model.predict(input_array)
#                 closing_price = round(pred[0][0], 2)
#             except Exception as e:
#                 closing_price = f"Error: {e}"

#     return render_template("index.html", prediction=prediction, recommendation=recommendation,
#                            stock_name=stock_name, percentage_change=percentage_change,
#                            closing_price=closing_price)

@app.route("/", methods=["GET", "POST"])
def index():
    prediction = None
    recommendation = None
    stock_name = ""
    percentage_change = None
    closing_price = None
    nse_data = None  # <- store NSE values to send to template

    auto_data = {}
    if request.method == "POST":
        stock_name = request.form.get("stock_name")

        if stock_name:
            auto_data = get_latest_nse_data(stock_name)

        if 'announcement' in request.form:
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

        elif 'fetch_nse' in request.form:
            try:
                nse_data = get_latest_nse_data(stock_name)
                if not nse_data:
                    prediction = f"❌ Could not fetch NSE data for {stock_name}."
            except Exception as e:
                prediction = f"⚠️ Error fetching NSE data: {e}"

        elif 'predict_price' in request.form:
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

    return render_template("index.html", prediction=prediction, recommendation=recommendation,
                       stock_name=stock_name, percentage_change=percentage_change,
                       closing_price=closing_price, auto_data=auto_data)


if __name__ == "__main__":
    app.run(debug=True)

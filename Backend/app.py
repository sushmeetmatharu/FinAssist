from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import os

app = Flask(__name__)
CORS(app)

model = None
vectorizer = None

# Try to load the model and vectorizer
try:
    bundle = joblib.load(r"C:\Users\Sushmeet Kaur\OneDrive\Desktop\FinAssist\announcements_nlp_model.pkl")
    model = bundle.get("model", None)
    vectorizer = bundle.get("vectorizer", None)
except Exception as e:
    print(f"Error loading model: {e}")

@app.route('/predict-announcement', methods=['POST'])
def predict_announcement():
    if model is None or vectorizer is None:
        return jsonify({"error": "Model or vectorizer not loaded. Likely due to version mismatch. Retrain or downgrade Python."}), 500

    data = request.json
    announcement_text = data.get("announcement", "")

    if not announcement_text:
        return jsonify({"error": "No announcement text provided."}), 400

    try:
        vect_text = vectorizer.transform([announcement_text])
        predicted_change = model.predict(vect_text)[0]
        return jsonify({"percentage_change": round(predicted_change, 2)})
    except Exception as e:
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)

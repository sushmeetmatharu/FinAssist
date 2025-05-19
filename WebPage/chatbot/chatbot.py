from llama_cpp import Llama
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS

# Load Mistral model
llm = Llama(
    model_path = r"D:\Downloads\mistral-7b-instruct-v0.1.Q4_K_M.gguf", 
    n_ctx=2048,  # Set appropriate context length
    n_threads=6,  # Use depending on your CPU cores
    verbose=True
)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")

    prompt = f"[INST] {user_message.strip()} [/INST]"

    response = llm(prompt, max_tokens=256, stop=["</s>"])
    answer = response["choices"][0]["text"].strip()

    return jsonify({"response": answer})

if __name__ == "__main__":
    app.run(port=5005)

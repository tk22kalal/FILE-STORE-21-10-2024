from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
import requests

app = Flask(__name__)

# Load environment variables
load_dotenv()
rapidapi_key = os.getenv("RAPIDAPI_KEY")
api_url = "https://chat-gpt26.p.rapidapi.com/"

# Temporary in-memory storage for PDF data
pdf_data_store = {}

# Endpoint to receive PDF data from Telegram bot
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    data = request.json
    user_id = data["user_id"]
    pdf_text = data["pdf_text"]
    chunks = data["chunks"]

    # Store the PDF content and chunks in memory
    pdf_data_store[user_id] = {"text": pdf_text, "chunks": chunks}
    return jsonify({"status": "success"})

# Endpoint for the chat interface
@app.route('/chatpdf', methods=['GET'])
def chatpdf():
    user_id = request.args.get('user_id')
    return render_template('chat.html', user_id=user_id)

# API for answering questions
@app.route('/answer_question', methods=['POST'])
def answer_question():
    user_id = request.json['user_id']
    question = request.json['question']

    # Retrieve the user's PDF data
    pdf_data = pdf_data_store.get(user_id)
    if not pdf_data:
        return jsonify({"error": "No PDF data found for this user."}), 404

    chunks = pdf_data['chunks']
    
    # Prepare the API headers
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "chat-gpt26.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    # Process each chunk through RapidAPI GPT-3.5 for question answering
    combined_response = ""
    for chunk in chunks:
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": f"{chunk}\n\nQuestion: {question}"}
            ]
        }
        response = requests.post(api_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and data["choices"]:
                answer = data["choices"][0]["message"]["content"]
                combined_response += answer + "\n\n"
        else:
            return jsonify({"error": "Error processing with RapidAPI GPT model."}), response.status_code

    return jsonify({"answer": combined_response.strip()})

if __name__ == '__main__':
    app.run(debug=True)

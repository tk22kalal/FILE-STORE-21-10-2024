from flask import Flask, request, jsonify, render_template
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI
import os
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

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

    # Load LLM with API key and perform question answering
    llm = OpenAI(api_key=openai_api_key)
    chain = load_qa_chain(llm, chain_type="stuff")
    response = chain.run(input_documents=chunks, question=question)

    return jsonify({"answer": response})

if __name__ == '__main__':
    app.run(debug=True)

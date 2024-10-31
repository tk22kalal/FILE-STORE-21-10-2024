from pyrogram import Client, filters
import fitz  # PyMuPDF
import requests  # For API calls

# Caploit API Endpoint and Headers
CAPLOIT_API_ENDPOINT = "https://api.copilot.com"
CAPLOIT_API_KEY = "3315f09244304402921dbe5e9b9dc3df.83f2378c800a261e"
HEADERS = {
    "Authorization": f"Bearer {CAPLOIT_API_KEY}",
    "Content-Type": "application/json"
}

# Function to extract text by page from PDF
def extract_pdf_text_by_page(pdf_path):
    text_by_page = {}
    with fitz.open(pdf_path) as pdf:
        for page_num in range(len(pdf)):
            text_by_page[page_num] = pdf[page_num].get_text()
    return text_by_page

# Function to find relevant pages based on query
def find_relevant_pages(query, text_by_page):
    relevant_pages = []
    for page_num, text in text_by_page.items():
        if query.lower() in text.lower():
            relevant_pages.append(page_num)
    return relevant_pages

# Function to create text chunks
def create_text_chunks(text, chunk_size=500):
    words = text.split()
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
    return chunks

# Function to query Caploit API
def query_caploit_api(query_text):
    response = requests.post(
        CAPLOIT_API_ENDPOINT,
        headers=HEADERS,
        json={"query": query_text}
    )
    if response.status_code == 200:
        return response.json().get("answer", "")
    else:
        return "Error: Could not retrieve answer from Caploit API."

@Client.on_message(filters.document & filters.private)
async def handle_pdf(client, message):
    if message.document.mime_type == "application/pdf":
        # Download PDF
        pdf_path = await message.download()
        # Reply to prompt chat mode
        await message.reply_text("Send /chatpdf to start querying this PDF.")
        
        # Store the file path to keep track of the PDF file for this user
        client.user_data[message.from_user.id] = pdf_path

@Client.on_message(filters.command("chatpdf") & filters.private)
async def start_pdf_chat(client, message):
    user_id = message.from_user.id
    
    # Check if PDF file exists for the user
    pdf_path = client.user_data.get(user_id)
    if not pdf_path:
        await message.reply_text("Please send a PDF file first.")
        return
    
    await message.reply_text("Please ask your question about the PDF.")
    
    # Listen for the user’s question
    @Client.on_message(filters.text & filters.private)
    async def handle_question(client, question_message):
        query = question_message.text
        text_by_page = extract_pdf_text_by_page(pdf_path)
        
        # Find pages related to the query
        relevant_pages = find_relevant_pages(query, text_by_page)
        
        # Gather text from relevant pages and create chunks
        text_to_analyze = " ".join([text_by_page[page] for page in relevant_pages])
        text_chunks = create_text_chunks(text_to_analyze)
        
        # Process each chunk with Caploit API
        answers = []
        for chunk in text_chunks:
            response = query_caploit_api(chunk)
            answers.append(response)
        
        # Send final answer back to the user
        final_answer = " ".join(answers)
        await question_message.reply_text(f"Answer: {final_answer}")

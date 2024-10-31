
import logging
from pyrogram import Client, filters
import fitz  # PyMuPDF
import requests  # For API calls

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caploit API Endpoint and Headers
CAPLOIT_API_ENDPOINT = "https://api.copilot.com"
CAPLOIT_API_KEY = "3315f09244304402921dbe5e9b9dc3df.83f2378c800a261e"
HEADERS = {
    "Authorization": f"Bearer {CAPLOIT_API_KEY}",
    "Content-Type": "application/json"
}

# Function to extract text by page from PDF
def extract_pdf_text_by_page(pdf_path):
    logger.info("Extracting text from PDF by page.")
    text_by_page = {}
    with fitz.open(pdf_path) as pdf:
        for page_num in range(len(pdf)):
            text_by_page[page_num] = pdf[page_num].get_text()
            logger.info(f"Extracted text for page {page_num}.")
    return text_by_page

# Function to find relevant pages based on query
def find_relevant_pages(query, text_by_page):
    logger.info(f"Finding relevant pages for the query: {query}")
    relevant_pages = []
    for page_num, text in text_by_page.items():
        if query.lower() in text.lower():
            relevant_pages.append(page_num)
            logger.info(f"Query found on page {page_num}.")
    logger.info(f"Relevant pages found: {relevant_pages}")
    return relevant_pages

# Function to create text chunks
def create_text_chunks(text, chunk_size=500):
    logger.info("Creating text chunks.")
    words = text.split()
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
    logger.info(f"Created {len(chunks)} chunks.")
    return chunks

# Function to query Caploit API
def query_caploit_api(query_text):
    logger.info("Querying Caploit API.")
    try:
        response = requests.post(
            CAPLOIT_API_ENDPOINT,
            headers=HEADERS,
            json={"query": query_text}
        )
        if response.status_code == 200:
            answer = response.json().get("answer", "")
            logger.info("Successfully retrieved answer from Caploit API.")
            return answer
        else:
            logger.error(f"Caploit API error: {response.status_code} - {response.text}")
            return "Error: Could not retrieve answer from Caploit API."
    except Exception as e:
        logger.error(f"Exception occurred while querying Caploit API: {e}")
        return "Error: An exception occurred."

@Client.on_message(filters.document & filters.private)
async def handle_pdf(client, message):
    logger.info("Received document.")
    if message.document.mime_type == "application/pdf":
        logger.info("Document is a PDF.")
        
        # Download PDF
        pdf_path = await message.download()
        logger.info(f"PDF downloaded to {pdf_path}")
        
        # Reply to prompt chat mode
        await message.reply_text("Send /chatpdf to start querying this PDF.")
        
        # Store the file path to keep track of the PDF file for this user
        client.user_data[message.from_user.id] = pdf_path
    else:
        logger.info("Document is not a PDF.")

@Client.on_message(filters.command("chatpdf") & filters.private)
async def start_pdf_chat(client, message):
    user_id = message.from_user.id
    logger.info("Received /chatpdf command.")
    
    # Check if PDF file exists for the user
    pdf_path = client.user_data.get(user_id)
    if not pdf_path:
        logger.warning("No PDF file found for user.")
        await message.reply_text("Please send a PDF file first.")
        return
    
    await message.reply_text("Please ask your question about the PDF.")
    
    # Listen for the user’s question
    @Client.on_message(filters.text & filters.private)
    async def handle_question(client, question_message):
        query = question_message.text
        logger.info(f"Received question: {query}")
        
        # Extract text from the PDF
        text_by_page = extract_pdf_text_by_page(pdf_path)
        
        # Find pages related to the query
        relevant_pages = find_relevant_pages(query, text_by_page)
        
        if not relevant_pages:
            logger.info("No relevant pages found for the query.")
            await question_message.reply_text("No relevant pages found in the PDF for your query.")
            return
        
        # Gather text from relevant pages and create chunks
        text_to_analyze = " ".join([text_by_page[page] for page in relevant_pages])
        text_chunks = create_text_chunks(text_to_analyze)
        
        # Process each chunk with Caploit API
        answers = []
        for chunk in text_chunks:
            response = query_caploit_api(chunk)
            answers.append(response)
            logger.info(f"Received answer chunk: {response}")
        
        # Send final answer back to the user
        final_answer = " ".join(answers)
        logger.info(f"Final answer compiled: {final_answer}")
        await question_message.reply_text(f"Answer: {final_answer}")

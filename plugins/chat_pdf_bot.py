import os
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
import requests

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Set up the Telegram bot
API_URL = "https://afrahtafreeh.site/upload_pdf"  # Server URL to upload and process PDF

@Client.on_message(filters.command("chatpdf") & filters.document)
async def chatpdf_handler(client: Client, message: Message):
    pdf = message.document
    
    if pdf and pdf.file_name.endswith('.pdf'):
        file_path = await client.download_media(pdf)
        user_id = message.from_user.id

        # Process PDF
        with open(file_path, "rb") as f:
            pdf_reader = PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        
        # Split into chunks
        text_splitter = CharacterTextSplitter(separator="\n", chunk_size=1000, chunk_overlap=200, length_function=len)
        chunks = text_splitter.split_text(text)

        # Create embeddings with OpenAI API key
        embeddings = OpenAIEmbeddings(api_key=openai_api_key)
        knowledge_base = FAISS.from_texts(chunks, embeddings)

        # Send data to server
        response = requests.post(API_URL, json={"user_id": user_id, "pdf_text": text, "chunks": chunks})
        
        if response.status_code == 200:
            # Send a message with a link to the web app
            button = InlineKeyboardMarkup([[InlineKeyboardButton("CLICK ON THE BELOW BUTTON", url=f"https://afrahtafreeh.site/chatpdf?user_id={user_id}")]])
            await message.reply("Click on the button below to start chatting with your PDF!", reply_markup=button)
        
        # Clean up
        os.remove(file_path)
    else:
        await message.reply("Please upload a valid PDF file.")

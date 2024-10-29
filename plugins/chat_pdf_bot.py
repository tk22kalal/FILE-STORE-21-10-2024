import os
import time
import requests
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai.embeddings import OpenAIEmbeddings  # Updated import path
from langchain.vectorstores import FAISS
from Adarsh.bot import StreamBot

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

API_URL = "https://afrahtafreeh.site/upload_pdf"

@StreamBot.on_message(filters.command("chatpdf") & filters.document)
async def chatpdf_handler(client: Client, message: Message):
    pdf = message.document
    await message.reply("📄 PDF received. Processing...")  # Notify user about PDF receipt

    if pdf and pdf.file_name.endswith('.pdf'):
        try:
            # Download the PDF
            file_path = await client.download_media(pdf)
            print("Downloaded PDF to:", file_path)  # Debug log

            # Extract text from the PDF
            with open(file_path, "rb") as f:
                pdf_reader = PdfReader(f)
                text = "".join(page.extract_text() for page in pdf_reader.pages)
                
            # Split PDF text into chunks
            text_splitter = CharacterTextSplitter(
                separator="\n",
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len
            )
            chunks = text_splitter.split_text(text)
            await message.reply("Text extracted and split into chunks. Generating embeddings...")  # Notify user

            # Retry logic for embedding requests with exponential backoff
            max_retries = 5
            embeddings = None
            for attempt in range(max_retries):
                try:
                    embeddings = OpenAIEmbeddings()
                    knowledge_base = FAISS.from_texts(chunks, embeddings)
                    break
                except openai.error.RateLimitError as e:
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        await message.reply("🚫 Quota limit exceeded for embeddings. Please try again later.")
                        return

            # Send text to server and handle response
            response = requests.post(API_URL, json={"user_id": message.from_user.id, "pdf_text": text})
            if response.status_code == 200:
                url = f"https://afrahtafreeh.site/chatpdf?user_id={message.from_user.id}"
                button = InlineKeyboardMarkup([[InlineKeyboardButton("CLICK HERE", url=url)]])
                await message.reply("Click the button below to chat with your PDF!", reply_markup=button)
                print("Sent chat link to user.")  # Debug log
            else:
                await message.reply("Failed to process PDF on the server.")
                print("Server response error:", response.text)  # Debug log

            # Clean up downloaded PDF file
            os.remove(file_path)
        except Exception as e:
            print("Error processing PDF:", e)  # Debug log
            await message.reply("An error occurred while processing your PDF.")
    else:
        await message.reply("Please upload a valid PDF file.")  # Inform user if invalid format

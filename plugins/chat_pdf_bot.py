import os
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
import requests
from Adarsh.bot import StreamBot

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
API_URL = "https://afrahtafreeh.site/upload_pdf"

# Dictionary to store file paths for users
user_files = {}

@StreamBot.on_message(filters.document)
async def document_handler(client: Client, message: Message):
    pdf = message.document
    if pdf and pdf.file_name.endswith('.pdf'):
        try:
            # Download the PDF file and store the path
            file_path = await client.download_media(pdf)
            user_files[message.from_user.id] = file_path  # Store file path
            await message.reply("PDF received! Now reply to this message with /chatpdf to start processing.")
            print("PDF received and stored for user:", message.from_user.id)
        except Exception as e:
            print("Error downloading PDF:", e)
            await message.reply("Failed to download PDF. Please try again.")
    else:
        await message.reply("Only PDF files are supported. Please upload a PDF.")

@StreamBot.on_message(filters.command("chatpdf") & filters.reply)
async def chatpdf_handler(client: Client, message: Message):
    user_id = message.from_user.id
    file_path = user_files.get(user_id)

    # Ensure the file exists for the user
    if not file_path:
        await message.reply("No PDF found. Please upload a PDF and then reply with /chatpdf.")
        return

    try:
        # Start processing with progress messages
        await message.reply("Starting PDF processing... 0% complete.")
        
        # Load and extract PDF text with progress updates
        with open(file_path, "rb") as f:
            pdf_reader = PdfReader(f)
            pages = pdf_reader.pages
            total_pages = len(pages)
            text = ""
            for i, page in enumerate(pages):
                text += page.extract_text()
                progress = int((i + 1) / total_pages * 50)  # First 50% for text extraction
                await message.reply(f"Extracting text... {progress}% complete.")

        # Process PDF text into chunks and create embeddings
        text_splitter = CharacterTextSplitter(separator="\n", chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(text)
        embeddings = OpenAIEmbeddings()
        knowledge_base = FAISS.from_texts(chunks, embeddings)

        await message.reply("Processing embeddings... 75% complete.")
        
        # Send text to the server and update progress
        response = requests.post(API_URL, json={"user_id": user_id, "pdf_text": text})
        if response.status_code == 200:
            url = f"https://afrahtafreeh.site/chatpdf?user_id={user_id}"
            button = InlineKeyboardMarkup([[InlineKeyboardButton("CLICK HERE", url=url)]])
            await message.reply("Processing complete! 100% done. Click the button below to chat with your PDF!", reply_markup=button)
        else:
            await message.reply("Failed to process PDF. Please try again.")
            print("Server response error:", response.text)

        # Clean up
        os.remove(file_path)
        del user_files[user_id]  # Remove file path from dictionary after processing

    except Exception as e:
        print("Error processing PDF:", e)
        await message.reply("An error occurred while processing your PDF.")

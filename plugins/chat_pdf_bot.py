import os
import time
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS
import requests
from Adarsh.bot import StreamBot

# Load environment variables
load_dotenv()
api_key = os.getenv("RAPIDAPI_KEY")  # Store your RapidAPI key here
API_URL = "https://chat-gpt26.p.rapidapi.com/"

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
                text += page.extract_text() or ""
                progress = int((i + 1) / total_pages * 50)  # First 50% for text extraction
                await message.reply(f"Extracting text... {progress}% complete.")

        # Process PDF text into chunks
        text_splitter = CharacterTextSplitter(separator="\n", chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(text)

        # Prepare a response using the RapidAPI GPT model
        await message.reply("Processing with RapidAPI GPT model... 75% complete.")
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "chat-gpt26.p.rapidapi.com",
            "Content-Type": "application/json"
        }

        # Generate responses based on PDF content
        responses = []
        for chunk in chunks:
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": chunk}]
            }
            response = requests.post(API_URL, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and data["choices"]:
                    responses.append(data["choices"][0]["message"]["content"])
            else:
                print("Error processing with GPT API:", response.status_code, response.text)
                await message.reply("Failed to process with RapidAPI GPT model. Please try again later.")
                return

        # Combine the responses into a single string
        final_response = "\n\n".join(responses)

        # Send response to the user
        button_url = f"https://afrahtafreeh.site/chatpdf?user_id={user_id}"
        button = InlineKeyboardMarkup([[InlineKeyboardButton("CLICK HERE", url=button_url)]])
        await message.reply("Processing complete! 100% done. Click the button below to chat with your PDF!", reply_markup=button)

        # Clean up
        os.remove(file_path)
        del user_files[user_id]  # Remove file path from dictionary after processing

    except Exception as e:
        print("Error processing PDF:", e)
        await message.reply("An error occurred while processing your PDF.")

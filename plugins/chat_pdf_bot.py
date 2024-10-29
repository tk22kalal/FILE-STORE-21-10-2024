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

@StreamBot.on_message(filters.command("chatpdf") & filters.document)
async def chatpdf_handler(client: Client, message: Message):
    pdf = message.document
    print("Received /chatpdf command with document:", pdf)  # Debug log

    if pdf and pdf.file_name.endswith('.pdf'):
        try:
            file_path = await client.download_media(pdf)
            print("Downloaded PDF to:", file_path)  # Debug log

            # Process PDF text and send to the server
            with open(file_path, "rb") as f:
                pdf_reader = PdfReader(f)
                text = "".join(page.extract_text() for page in pdf_reader.pages)
            
            # Send text to server and handle response
            response = requests.post(API_URL, json={"user_id": message.from_user.id, "pdf_text": text})
            if response.status_code == 200:
                url = f"https://afrahtafreeh.site/chatpdf?user_id={message.from_user.id}"
                button = InlineKeyboardMarkup([[InlineKeyboardButton("CLICK HERE", url=url)]])
                await message.reply("Click the button below to chat with your PDF!", reply_markup=button)
                print("Sent chat link to user.")  # Debug log
            else:
                await message.reply("Failed to process PDF.")
                print("Server response error:", response.text)  # Debug log

            os.remove(file_path)  # Clean up
        except Exception as e:
            print("Error processing PDF:", e)  # Debug log
            await message.reply("An error occurred while processing your PDF.")
    else:
        print("No PDF file found or incorrect format.")  # Debug log
        await message.reply("Please upload a valid PDF file.")


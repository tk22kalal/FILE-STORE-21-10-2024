

from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from pyrogram.enums import ParseMode
from config import ADMINS, BOT_STATS_TEXT, USER_REPLY_TEXT, AI, OPENAI_API, AI_LOGS
from datetime import datetime
from helper_func import get_readable_time
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from pyrogram import Client
import openai
import google.generativeai as genai
from database.database import full_userbase
import PyPDF2
import io
import pytesseract
from PIL import Image
import pdf2image

# Configure the Google Gemini API Key
genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")

# Keyboard and button setup
buttonz = ReplyKeyboardMarkup([["newchat⚡️"]], resize_keyboard=True)
inline_button = InlineKeyboardMarkup([[InlineKeyboardButton("🩺 MEDICAL LECTURES", url="https://sites.google.com/view/pavoladdder")]])

# Dictionary to store user conversations, PDF content, selected topic, and relevant pages
user_conversations = {}
user_pdfs = {}
user_selected_topic = {}

@Client.on_message(filters.document)
async def pdf_handler(client: Client, message: Message):
    """Handle PDF uploads, extract text, and prompt user to select a topic."""
    if message.document.file_name.endswith(".pdf"):
        file_id = message.document.file_id
        file = await client.download_media(file_id)
        
        # Initialize PDF text variable
        pdf_text = ""
        
        try:
            # Extract text directly from text-based PDFs
            with open(file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    pdf_text += page.extract_text() or ""

            # If text is missing, convert to images and use OCR
            if not pdf_text.strip():
                images = pdf2image.convert_from_path(file)
                for image in images:
                    text = pytesseract.image_to_string(image)
                    pdf_text += text
            
            user_id = message.from_user.id
            user_pdfs[user_id] = pdf_text
            await message.reply("PDF processed successfully. Please reply with the topic you’d like to explore.")

        except Exception as e:
            await message.reply("Error processing the PDF. Please try again.")
            print(f"Error processing PDF: {e}")
    else:
        await message.reply("Please upload a PDF document.")

@Client.on_message(filters.text & filters.reply)
async def topic_selection(client: Client, message: Message):
    """Handle topic selection and find relevant pages."""
    user_id = message.from_user.id
    if user_id in user_pdfs:
        topic = message.text.strip().lower()
        pdf_content = user_pdfs[user_id]
        
        # Search for up to 10 pages relevant to the selected topic
        relevant_pages = []
        with io.StringIO(pdf_content) as text_stream:
            pages = text_stream.getvalue().split("\n")
            for page_num, content in enumerate(pages, start=1):
                if topic in content.lower() and len(relevant_pages) < 10:
                    relevant_pages.append((page_num, content))
        
        if relevant_pages:
            user_selected_topic[user_id] = relevant_pages
            await message.reply("Topic found. Now please reply with a specific question related to this topic.")
        else:
            await message.reply("Couldn't find relevant pages for the selected topic. Please try a different topic.")
    else:
        await message.reply("Please upload a PDF first.")

def chunk_text(text, chunk_size=200):
    """Split text into smaller chunks for easier processing."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

@Client.on_message(filters.text & filters.reply)
async def question_handler(client: Client, message: Message):
    """Answer questions about the selected topic using the Gemini API."""
    user_id = message.from_user.id
    if user_id in user_selected_topic:
        question = message.text.strip().lower()
        topic_pages = user_selected_topic[user_id]
        
        # Combine content of selected pages for prompt
        combined_content = "\n".join([content for _, content in topic_pages])
        text_chunks = chunk_text(combined_content, chunk_size=1000)

        # Prepare prompt for the Gemini API
        formatted_prompt = (
            "Provide a clear and structured answer in notes format with headings:\n"
            "• Main Topic\n"
            "  ✓ Key Points\n"
            "  ● Details\n"
            "  ○ Examples if relevant\n\n"
            f"Content:\n{combined_content}\n\nQuestion: {question}"
        )

        try:
            model = genai.GenerativeModel(
                model_name="gemini-pro",
                generation_config={
                    "temperature": 0.8,
                    "top_p": 1,
                    "top_k": 1,
                    "max_output_tokens": 800,
                },
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                ]
            )
            # Generate response from the Gemini API
            response = model.generate_content([formatted_prompt])

            # Send the structured response back to the user
            await client.send_message(
                chat_id=message.chat.id,
                text=response.text,
                parse_mode=ParseMode.HTML,
                reply_markup=inline_button
            )

        except Exception as e:
            await message.reply("Error generating a response. Please try again.")
            print(f"Error generating response: {e}")
    else:
        await message.reply("Please select a topic first by uploading a PDF and specifying a topic.")

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

# Dictionary to store user conversations, PDF content, and selected topic data
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
            # Try extracting text directly (for text-based PDFs)
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
            await message.reply("PDF processed successfully. Please enter the topic you'd like to explore.")
        
        except Exception as e:
            await message.reply("Error processing the PDF. Please try again.")
            print(f"Error processing PDF: {e}")
    else:
        await message.reply("Please upload a PDF document.")

@Client.on_message(filters.text & filters.reply)
async def topic_selection(client: Client, message: Message):
    """Prompt the user for a topic, search for relevant pages, and request a question."""
    user_id = message.from_user.id
    if user_id in user_pdfs:
        topic = message.text.strip().lower()
        pdf_content = user_pdfs[user_id]

        # Search for pages relevant to the topic and limit to 10 pages
        topic_pages = []
        with io.StringIO(pdf_content) as text_stream:
            for page_num, content in enumerate(text_stream.getvalue().split("\n"), start=1):
                if topic in content.lower() and len(topic_pages) < 10:
                    topic_pages.append((page_num, content))
        
        if topic_pages:
            user_selected_topic[user_id] = topic_pages
            await message.reply("Topic selected. Please ask a specific question related to this topic.")
        else:
            await message.reply("Couldn't find any relevant pages for the selected topic.")
    else:
        await message.reply("Please upload a PDF first.")

@Client.on_message(filters.text & filters.reply)
async def question_handler(client: Client, message: Message):
    """Respond to the user's question by generating answers from relevant PDF pages."""
    user_id = message.from_user.id
    if user_id in user_selected_topic:
        question = message.text.strip().lower()
        topic_pages = user_selected_topic[user_id]

        # Prepare content from selected pages for the Gemini prompt
        prompt_text = "\n".join([content for _, content in topic_pages])
        formatted_prompt = (
            "Explain in a simple and structured notes format with headings:\n"
            "• Topic\n"
            "  ✓ Key Points\n"
            "  ● Details\n"
            "  ○ Examples if applicable\n"
            f"\n{prompt_text}\n\nQuestion: {question}"
        )

        # Generate response using the Gemini API
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
            response = model.generate_content([formatted_prompt])

            # Send response to the user
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

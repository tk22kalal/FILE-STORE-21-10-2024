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
import requests
import google.generativeai as genai
from google.cloud import vision
import io
from database.database import full_userbase
import PyPDF2
from PIL import Image
import pdf2image

# Configure Google Gemini API and Vision client
genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/gen-lang-client-0707503202-21d07fd84f57.json")

# Setup keyboards
buttonz = ReplyKeyboardMarkup([["newchat⚡️"]], resize_keyboard=True)
inline_button = InlineKeyboardMarkup([[InlineKeyboardButton("🩺 MEDICAL LECTURES", url="https://sites.google.com/view/pavoladdder")]])

user_contexts = {}  # Store user contexts for follow-up questions
user_page_ranges = {}  # Store page ranges for each user
user_pdfs = {}  # Store processed PDFs for each user

@Bot.on_message(filters.command('clear') & filters.user(ADMINS))
async def clear(bot: Bot, message: Message):
    chat_id = message.chat.id
    async for msg in bot.search_messages(chat_id, limit=100):
        if msg.from_user.is_bot and msg.message_id != message.message_id:
            await msg.delete()
    await message.reply("Bot message history cleared.")

@Bot.on_message(filters.command('stats') & filters.user(ADMINS))
async def stats(bot: Bot, message: Message):
    now = datetime.now()
    delta = now - bot.uptime
    time = get_readable_time(delta.seconds)
    await message.reply(BOT_STATS_TEXT.format(uptime=time))

@Client.on_message(filters.document)
async def pdf_handler(client: Client, message: Message):
    """Handle PDF upload and prompt user for page range selection or skipping."""
    if message.document.file_name.endswith(".pdf"):
        user_id = message.from_user.id
        await message.reply("Please type the range of pages in the format (e.g., 0-5, 6-12, 3-4) or type /skip if you want to process the entire PDF.")

        # Save the file for future processing
        file_id = message.document.file_id
        user_pdfs[user_id] = await client.download_media(file_id)

@Client.on_message(filters.text & filters.reply)
async def range_response_handler(client: Client, message: Message):
    """Handle user response for page range input or skip command."""
    user_id = message.from_user.id
    original_message = message.reply_to_message

    if "Please type the range of pages" in original_message.text:
        range_text = message.text.strip()

        if range_text.lower() == "/skip":
            user_page_ranges[user_id] = None  # No range specified, process all pages
        else:
            try:
                page_ranges = []
                for part in range_text.split(","):
                    start, end = map(int, part.split("-"))
                    page_ranges.extend(range(start, end + 1))
                user_page_ranges[user_id] = page_ranges
            except ValueError:
                await message.reply("Invalid format. Please type the range as specified (e.g., 0-5, 6-12) or type /skip.")
                return

        # Proceed with processing the PDF after range is set or skipped
        await process_pdf(client, message, user_id)
        await message.reply("PDF processed successfully. You can now ask questions about its content.")

async def process_pdf(client: Client, message: Message, user_id: int):
    """Process the PDF based on specified or default page range."""
    pdf_path = user_pdfs.get(user_id)
    pdf_text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            num_pages = len(reader.pages)
            page_range = user_page_ranges.get(user_id, range(num_pages))

            for page_num in page_range:
                if page_num < num_pages:
                    page = reader.pages[page_num]
                    page_text = page.extract_text() or ""
                    
                    # Convert to image and apply OCR if needed
                    images = pdf2image.convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1, dpi=300)
                    for image in images:
                        image_bytes = io.BytesIO()
                        image.save(image_bytes, format='JPEG')
                        vision_image = vision.Image(content=image_bytes.getvalue())
                        ocr_response = vision_client.text_detection(image=vision_image)
                        ocr_text = ocr_response.full_text_annotation.text
                        page_text += ocr_text

                    # Use Gemini AI for missing/incomplete text
                    if len(page_text.strip()) < 50:
                        prompt_text = f"The text on page {page_num + 1} is unclear or partially missing. Please provide an explanation in simple notes."
                        model = genai.GenerativeModel(model_name="gemini-pro", generation_config={"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 800})
                        response = model.generate_content([prompt_text])
                        page_text += response.text

                    pdf_text += f"Page {page_num + 1}:\n{page_text}\n\n"

        user_contexts[user_id] = pdf_text  # Save the processed PDF content
    except Exception as e:
        await message.reply("Error processing the PDF. Please try again.")
        print(f"Error processing PDF: {e}")

@Client.on_message(filters.text & filters.private)
async def question_handler(client: Client, message: Message):
    """Handle questions based on the processed PDF content."""
    user_id = message.from_user.id
    context_text = user_contexts.get(user_id, "")

    if not context_text:
        await message.reply("Please upload a PDF first to ask questions about its content.")
        return

    question = message.text.lower()
    if message.reply_to_message:
        # Follow-up question - use the reply's text as the context
        context_text = message.reply_to_message.text

    # Generate AI response using PDF context
    prompt_text = f"{context_text}\n\nQuestion: {question}"
    formatted_prompt = (
        "Explain in simple language, use bold (do not include **), in notes format, and add sections as follows:\n"
        "• Main Topic (always bold)\n\n  ● Key Points\n  ○ Details\n  ✓ Examples\n\n"
        f"{prompt_text}"
    )

    model = genai.GenerativeModel(model_name="gemini-pro", generation_config={"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 1000})
    response = model.generate_content([formatted_prompt])
    formatted_response = response.text.replace("**", "<b>").replace("**", "</b>")

    # Save context for follow-up questions
    user_contexts[user_id] = formatted_response
    await client.send_message(chat_id=message.chat.id, text=formatted_response, reply_markup=inline_button)

def chunk_text(text, chunk_size=200):
    """Split text into manageable chunks."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

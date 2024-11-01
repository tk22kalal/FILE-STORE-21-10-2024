from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from pyrogram.enums import ParseMode
from config import ADMINS, BOT_STATS_TEXT, USER_REPLY_TEXT, AI, OPENAI_API, AI_LOGS
from datetime import datetime
from pyrogram.enums import ParseMode
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

# Configure the Google Gemini API Key and Vision
genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/gen-lang-client-0707503202-21d07fd84f57.json")

# Setup keyboard buttons
buttonz = ReplyKeyboardMarkup([["newchat⚡️"]], resize_keyboard=True)
inline_button = InlineKeyboardMarkup([[InlineKeyboardButton("🩺 MEDICAL LECTURES", url="https://sites.google.com/view/pavoladdder")]])

user_conversations = {}
user_pdfs = {}
user_context = {}  # Track conversation context for follow-up questions

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
    """Handle PDF uploads, extract text from both text and image-based PDFs, and store for the user."""
    if message.document.file_name.endswith(".pdf"):
        file_id = message.document.file_id
        file = await client.download_media(file_id)
        
        pdf_text = ""
        try:
            with open(file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                num_pages = len(reader.pages)

                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    page_text = page.extract_text() or ""

                    # Convert page to image and use Google Vision OCR
                    images = pdf2image.convert_from_path(file, first_page=page_num+1, last_page=page_num+1, dpi=300)
                    for image in images:
                        image_bytes = io.BytesIO()
                        image.save(image_bytes, format='JPEG')
                        vision_image = vision.Image(content=image_bytes.getvalue())

                        ocr_response = vision_client.text_detection(image=vision_image)
                        ocr_text = ocr_response.full_text_annotation.text
                        page_text += ocr_text

                    # If text is incomplete, generate content with Gemini AI
                    if len(page_text.strip()) < 50:
                        prompt_text = f"The text on page {page_num + 1} is unclear or partially missing. Provide an explanation in simple notes."
                        model = genai.GenerativeModel(
                            model_name="gemini-pro",
                            generation_config={"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 800}
                        )
                        response = model.generate_content([prompt_text])
                        page_text += response.text

                    pdf_text += f"Page {page_num + 1}:\n{page_text}\n\n"

            user_id = message.from_user.id
            user_pdfs[user_id] = pdf_text
            await message.reply("PDF processed successfully. Reply to this PDF with your question to ask about its content or ask directly without replying for follow-up questions.")

        except Exception as e:
            await message.reply("Error processing the PDF. Please try again.")
            print(f"Error processing PDF: {e}")
    else:
        await message.reply("Please upload a PDF document.")

def chunk_text(text, chunk_size=200):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


@Client.on_message(filters.text & filters.private)
async def pdf_question_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_pdfs:
        pdf_content = user_pdfs[user_id]
        
        if message.reply_to_message:
            if message.reply_to_message.from_user.is_bot:
                previous_answer = user_context.get(user_id, "")
                question = message.text

                prompt_text = f"{previous_answer}\n\nFollow-up Question: {question}"
            else:
                question = message.text.lower()
                user_context[user_id] = pdf_content

                chunks = chunk_text(pdf_content)
                relevant_chunks = [chunk for chunk in chunks if any(keyword in chunk.lower() for keyword in question.split())]
                prompt_text = " ".join(relevant_chunks)
        else:
            question = message.text.lower()
            user_context[user_id] = pdf_content
            
            chunks = chunk_text(pdf_content)
            relevant_chunks = [chunk for chunk in chunks if any(keyword in chunk.lower() for keyword in question.split())]
            prompt_text = " ".join(relevant_chunks)
        
        formatted_prompt = (
            "Explain in easy language, in point wise, dont use # or * like symbols and use below symbols for different levels of headings (h1, h2, h3, h4, ...etc) which are in strong bold text:\n"
            "● , ○, ✓, •, * or NUMBERS or .... \n\n"
            f"{prompt_text}\n\nQuestion: {question}"
        )
        
        # Generate content with Gemini AI
        generation_config = {"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 1000}
        model = genai.GenerativeModel(
            model_name="gemini-pro", generation_config=generation_config,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ]
        )

        
        response = model.generate_content([formatted_prompt])

        # Replace double asterisks with <b> and </b>
        parts = response.text.split("**")
        response_content = "".join(
            f"<b>{part}</b>" if index % 2 == 1 else part for index, part in enumerate(parts)
        )
        
        user_context[user_id] = response

        await client.send_message(
            chat_id=message.chat.id,
            parse_mode=ParseMode.HTML,
            text=response_content
        )
    else:
        await message.reply("Please upload a PDF first to ask questions about its content.")

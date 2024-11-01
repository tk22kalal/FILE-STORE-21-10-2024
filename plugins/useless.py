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

# Configure the Google Gemini API Key and Vision
genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/gen-lang-client-0707503202-21d07fd84f57.json")


# Setup keyboard buttons
buttonz = ReplyKeyboardMarkup([["newchat⚡️"]], resize_keyboard=True)
inline_button = InlineKeyboardMarkup([[InlineKeyboardButton("🩺 MEDICAL LECTURES", url="https://sites.google.com/view/pavoladdder")]])

user_conversations = {}
user_pdfs = {}
user_context = {}
user_page_ranges = {}  # Dictionary to store specified page ranges for each user

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
    """Prompt user to specify page range or process the full PDF on upload."""
    if message.document.file_name.endswith(".pdf"):
        user_id = message.from_user.id

        # Ask user for page range or to skip
        await message.reply("Please type the range of pages in the format (e.g., 0-5, 6-12, 3-4) or type /skip if you want to process the entire PDF.")
        
        # Wait for user's reply to determine page range or skip
        @Client.on_message(filters.text & filters.reply & filters.user(user_id))
        async def range_response_handler(client, reply_message: Message):
            range_text = reply_message.text.strip()

            if range_text.lower() == "/skip":
                user_page_ranges[user_id] = None  # No range specified, process all pages
                await process_pdf(client, message, user_id)
            else:
                try:
                    # Parse the page ranges from user input
                    page_ranges = []
                    for part in range_text.split(","):
                        start, end = map(int, part.split("-"))
                        page_ranges.extend(range(start, end + 1))
                    
                    user_page_ranges[user_id] = page_ranges  # Save the page range
                    await process_pdf(client, message, user_id)

                except ValueError:
                    await reply_message.reply("Invalid format. Please type the range as specified (e.g., 0-5, 6-12) or type /skip.")

async def process_pdf(client: Client, message: Message, user_id: int):
    """Process the PDF based on the user-specified page ranges or the entire document if no range specified."""
    file_id = message.document.file_id
    file = await client.download_media(file_id)
    pdf_text = ""
    try:
        with open(file, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            num_pages = len(reader.pages)
            page_range = user_page_ranges.get(user_id, range(num_pages))  # Use full range if user skipped

            for page_num in page_range:
                if page_num < num_pages:
                    page = reader.pages[page_num]
                    page_text = page.extract_text() or ""
                    
                    # Convert page to image and apply Google Vision OCR if text is missing or incomplete
                    images = pdf2image.convert_from_path(file, first_page=page_num+1, last_page=page_num+1, dpi=300)
                    for image in images:
                        image_bytes = io.BytesIO()
                        image.save(image_bytes, format='JPEG')
                        vision_image = vision.Image(content=image_bytes.getvalue())

                        ocr_response = vision_client.text_detection(image=vision_image)
                        ocr_text = ocr_response.full_text_annotation.text
                        page_text += ocr_text

                    # If text is still incomplete, generate additional content with Gemini AI
                    if len(page_text.strip()) < 50:
                        prompt_text = f"The text on page {page_num + 1} is unclear or partially missing. Provide an explanation in simple notes."
                        model = genai.GenerativeModel(
                            model_name="gemini-pro",
                            generation_config={"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 800}
                        )
                        response = model.generate_content([prompt_text])
                        page_text += response.text

                    pdf_text += f"Page {page_num + 1}:\n{page_text}\n\n"

        user_pdfs[user_id] = pdf_text  # Store processed PDF text
        await message.reply("PDF processed successfully. You can now ask questions about its content.")

    except Exception as e:
        await message.reply("Error processing the PDF. Please try again.")
        print(f"Error processing PDF: {e}")

def chunk_text(text, chunk_size=200):
    """Split text into manageable chunks for processing."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

@Client.on_message(filters.text & filters.private)
async def pdf_question_handler(client: Client, message: Message):
    """Handle user questions related to the processed PDF content."""
    user_id = message.from_user.id
    if user_id in user_pdfs:
        pdf_content = user_pdfs[user_id]
        question = message.text.lower()

        # Generate AI response based on the PDF content and user question without re-prompting for page range
        user_context[user_id] = pdf_content  # Set PDF as initial context if not already done
        
        chunks = chunk_text(pdf_content)
        relevant_chunks = [chunk for chunk in chunks if any(keyword in chunk.lower() for keyword in question.split())]
        prompt_text = " ".join(relevant_chunks)

        formatted_prompt = (
            "Explain in simple language, Main headings subheadings should be strong bold (do not include **), in notes format, add Google Gemini information to explain in easy words and use below formats according to needs(don't use *, -):\n"
            "• Main Topic (always bold)\n\n  ● Key Points\n  ○ Details\n  ✓ Examples\n\n"
            f"{prompt_text}\n\nQuestion: {question}"
        )

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
        formatted_response = response.text.replace("**", "<b>").replace("**", "</b>")

        # Store this response in the context for follow-up questions
        user_context[user_id] = formatted_response

        await client.send_message(
            chat_id=message.chat.id,
            text=formatted_response,
            reply_markup=inline_button
        )
    else:
        await message.reply("Please upload a PDF first to ask questions about its content.")



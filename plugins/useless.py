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

user_pdfs = {}
user_conversations = {}  
user_context = {}  # Track conversation context for follow-up questions

@Client.on_message(filters.document)
async def pdf_handler(client: Client, message: Message):
    """Handle PDF uploads and ask the user for a page range if the PDF is large."""
    if message.document.file_name.endswith(".pdf"):
        user_id = message.from_user.id
        file_id = message.document.file_id
        file_path = await client.download_media(file_id)  # Correctly get the file path

        # Check the number of pages first
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                num_pages = len(reader.pages)

                if num_pages > 10:  # Trigger split handling if PDF is large
                    await message.reply("Type the range of pages to process (e.g., 0-5, 8-11) or type /skip to process the entire PDF.")
                    user_pdfs[user_id] = file_path  # Store the path for use after user response
                else:
                    await process_pdf(client, message, file_path)  # Process the entire PDF if it's small

        except Exception as e:
            await message.reply("Error reading the PDF. Please try again.")
            print(f"Error reading PDF: {e}")
    else:
        await message.reply("Please upload a valid PDF document.")

@Client.on_message(filters.text & filters.private)
async def page_range_handler(client: Client, message: Message):
    """Handle the user input for page ranges or skipping."""
    user_id = message.from_user.id
    if user_id in user_pdfs:
        file_path = user_pdfs[user_id]

        if message.text.lower() == "/skip":
            # User chose to process the whole PDF
            await process_pdf(client, message, file_path)
            del user_pdfs[user_id]  # Remove stored file path after processing
        else:
            # User provided a range of pages
            try:
                page_ranges = parse_page_ranges(message.text)
                if page_ranges:
                    await process_pdf(client, message, file_path, page_ranges)
                    del user_pdfs[user_id]  # Remove stored file path after processing
                else:
                    await message.reply("Invalid page range format. Please type the range in the format 0-3, 4-7, etc., or type /skip.")
            except Exception as e:
                await message.reply("Error parsing page range. Please try again.")
                print(f"Error parsing page range: {e}")
    else:
        await message.reply("Please upload a PDF first to specify a page range.")

def parse_page_ranges(page_range_text):
    """Parse the user input for page ranges into a list of page indices."""
    page_ranges = []
    ranges = page_range_text.split(",")
    for range_str in ranges:
        if "-" in range_str:
            start, end = map(int, range_str.split("-"))
            page_ranges.extend(range(start, end + 1))
        else:
            page_ranges.append(int(range_str))
    return page_ranges

async def process_pdf(client: Client, message: Message, file_path, selected_pages=None):
    """Extract text and OCR content from the specified pages of the PDF."""
    user_id = message.from_user.id  # Ensure user_id is properly defined
    pdf_text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            num_pages = len(reader.pages)

            pages_to_process = selected_pages if selected_pages else range(num_pages)

            for page_num in pages_to_process:
                if page_num < num_pages:
                    page = reader.pages[page_num]
                    page_text = page.extract_text() or ""

                    # Convert page to image and use Google Vision OCR if needed
                    images = pdf2image.convert_from_path(file_path, first_page=page_num + 1, last_page=page_num + 1, dpi=300)
                    for image in images:
                        image_bytes = io.BytesIO()
                        image.save(image_bytes, format='JPEG')
                        vision_image = vision.Image(content=image_bytes.getvalue())

                        ocr_response = vision_client.text_detection(image=vision_image)
                        ocr_text = ocr_response.full_text_annotation.text
                        page_text += ocr_text

                    pdf_text += f"Page {page_num + 1}:\n{page_text}\n\n"

        user_pdfs[user_id] = pdf_text
        await message.reply("PDF processed successfully. Reply to this PDF with your question to ask about its content or ask directly without replying for follow-up questions.")

    except Exception as e:
        await message.reply("Error processing the PDF. Please try again.")
        print(f"Error processing PDF: {e}")

def chunk_text(text, chunk_size=200):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

@Client.on_message(filters.text & filters.private)
async def pdf_question_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_pdfs:
        pdf_content = user_pdfs[user_id]

        if message.reply_to_message:
            # If user is replying to an answer, continue from the context
            if message.reply_to_message.from_user.is_bot:
                previous_answer = user_context.get(user_id, "")
                question = message.text

                prompt_text = f"{previous_answer}\n\nFollow-up Question: {question}"
            else:
                # If replying to PDF or asking first question without reply, process PDF
                question = message.text.lower()
                user_context[user_id] = pdf_content  # Set PDF as the initial context

                chunks = chunk_text(pdf_content)
                relevant_chunks = [chunk for chunk in chunks if any(keyword in chunk.lower() for keyword in question.split())]
                prompt_text = " ".join(relevant_chunks)
        else:
            # Direct questions about the PDF
            question = message.text.lower()
            user_context[user_id] = pdf_content  # Set PDF as the initial context

            chunks = chunk_text(pdf_content)
            relevant_chunks = [chunk for chunk in chunks if any(keyword in chunk.lower() for keyword in question.split())]
            prompt_text = " ".join(relevant_chunks)

        # Formatting the prompt for AI generation
        formatted_prompt = (
            "Explain in simple language, Main headings subheadings should be strong bold (do not include **), in notes format, add google gemini information to explain in easy words and use below formats according to needs(dont use * , -):\n"
            "• Main Topic(always bold)\n\n  ● Key Points\n  ○ Details\n  ✓ Examples\n\n"
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

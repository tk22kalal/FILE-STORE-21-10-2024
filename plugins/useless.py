from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from pyrogram.enums import ParseMode
from config import ADMINS, BOT_STATS_TEXT, USER_REPLY_TEXT, AI, OPENAI_API, AI_LOGS
from datetime import datetime
from helper_func import get_readable_time
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from pyrogram import Client, filters
import openai
import requests
import google.generativeai as genai
from database.database import full_userbase
import PyPDF2
import io
import pytesseract
from PIL import Image
import PyPDF2
import pdf2image

# Configure the Google Gemini API Key
genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")

# Setup keyboard buttons
buttonz = ReplyKeyboardMarkup([["newchat⚡️"]], resize_keyboard=True)
inline_button = InlineKeyboardMarkup([[InlineKeyboardButton("🩺 MEDICAL LECTURES", url="https://sites.google.com/view/pavoladdder")]])

# Dictionary to store user/admin conversations and PDF content
user_conversations = {}
user_pdfs = {}

@Bot.on_message(filters.command('clear') & filters.user(ADMINS))
async def clear(bot: Bot, message: Message):
    """Clear the bot's message history in the chat."""
    chat_id = message.chat.id
    async for msg in bot.search_messages(chat_id, limit=100):
        if msg.from_user.is_bot and msg.message_id != message.message_id:
            await msg.delete()
    await message.reply("Bot message history cleared.")

@Bot.on_message(filters.command('stats') & filters.user(ADMINS))
async def stats(bot: Bot, message: Message):
    """Display bot uptime statistics."""
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
        
        # Initialize empty text variable
        pdf_text = ""

        try:
            # First, try extracting text directly from PDF (for text-based PDFs)
            with open(file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    pdf_text += page.extract_text() or ""

            # Check if text is missing (indicating image-based content)
            if not pdf_text.strip():
                # Convert PDF pages to images and apply OCR
                images = pdf2image.convert_from_path(file)
                for page_num, image in enumerate(images, start=1):
                    text = pytesseract.image_to_string(image)
                    
                    # If text extraction confidence is low or blurred text is detected
                    if len(text.strip()) < 50:
                        # Use Gemini AI to provide context if OCR fails
                        prompt_text = (
                            f"The text on page {page_num} is unclear or partially missing. "
                            "Based on surrounding context, provide an explanation in simple, structured notes format."
                        )
                        
                        model = genai.GenerativeModel(
                            model_name="gemini-pro",
                            generation_config={
                                "temperature": 0.8,
                                "top_p": 1,
                                "top_k": 1,
                                "max_output_tokens": 800,
                            }
                        )
                        response = model.generate_content([prompt_text])
                        text += response.text
                    
                    pdf_text += text

            user_id = message.from_user.id
            user_pdfs[user_id] = pdf_text
            await message.reply("PDF processed successfully. Reply to this PDF with your question to ask about its content.")

        except Exception as e:
            await message.reply("There was an error processing the PDF. Please try again.")
            print(f"Error processing PDF: {e}")
    else:
        await message.reply("Please upload a PDF document.")

def chunk_text(text, chunk_size=200):
    """Split text into chunks of a specified size."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

@Client.on_message(filters.reply & filters.text & filters.private)
async def pdf_question_handler(client: Client, message: Message):
    """Respond to questions about a PDF by finding relevant content and formatting as requested."""
    user_id = message.from_user.id
    if user_id in user_pdfs:
        question = message.text.lower()
        pdf_content = user_pdfs[user_id]
        
        # Determine if the question is about a specific page number
        if "page number" in question or "which page" in question:
            topic = question.replace("page number", "").replace("which page", "").strip()
            page_num = None
            with io.StringIO(pdf_content) as text_stream:
                for page, content in enumerate(text_stream.getvalue().split("\n"), start=1):
                    if topic.lower() in content.lower():
                        page_num = page
                        break
            if page_num:
                await message.reply(f"The topic '{topic}' is located on page {page_num}.")
            else:
                await message.reply(f"Couldn't find the topic '{topic}' in the PDF.")
            return
        
        # Chunk the PDF text for processing and response
        chunks = chunk_text(pdf_content)
        relevant_chunks = [chunk for chunk in chunks if any(keyword in chunk.lower() for keyword in question.split())]
        prompt_text = " ".join(relevant_chunks)

        # Format the response as structured notes with various symbols
        formatted_prompt = (
            "Explain in simple language, in notes format with the following structure if needed:\n"
            "• Main Topic\n"
            "  ● Key Points\n"
            "  ○ Details\n"
            "  ✓ Examples if needed\n"
            f"\n{prompt_text}\n\nQuestion: {question}"
        )

        # Generate response using Gemini model
        generation_config = {
            "temperature": 1,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 1000,
        }

        model = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config=generation_config,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ]
        )

        response = model.generate_content([formatted_prompt])
        lazy_response = response.text

        await client.send_message(
            chat_id=message.chat.id,
            text=lazy_response,
            parse_mode=ParseMode.HTML,
            reply_markup=inline_button
        )
    else:
        await message.reply("Please upload a PDF first and ask your question by replying to it.")

@Client.on_message((filters.private & filters.text) | (filters.command("newchat") | filters.regex('newchat⚡️')))
async def lazy_answer(client: Client, message: Message):
    """Standard Q&A using chat without PDF context."""
    if AI:
        user_id = message.from_user.id
        if user_id:
            try:
                if message.text.lower().strip() == "/newchat" or message.text.strip() == 'newchat⚡️':
                    user_conversations.pop(user_id, None)
                    user_pdfs.pop(user_id, None)
                    response_text = "New chat started. Ask me anything!"
                    await message.reply(response_text)
                    return

                user_messages = user_conversations.get(user_id, [])
                user_messages.append(message.text)
                prompt = "\n".join(user_messages)

                generation_config = {
                    "temperature": 1,
                    "top_p": 1,
                    "top_k": 1,
                    "max_output_tokens": 1000,
                }

                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                ]

                model = genai.GenerativeModel(
                    model_name="gemini-pro",
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
                prompt_parts = [prompt]

                response = model.generate_content(prompt_parts)

                users = await full_userbase()
                footer_credit = "<b>ADMIN ID:</b> - @talktomembbs_bot\n<b>Total Users:</b> {}".format(len(users))

                lazy_response = response.text

                await client.send_message(
                    chat_id=message.chat.id,
                    text=f"{lazy_response}\n{footer_credit}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=inline_button
                )

                user_conversations[user_id] = user_messages
            except Exception as error:
                print(error)
    else:
        return

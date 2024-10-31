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
    """Handle PDF uploads and prepare it for efficient topic-based querying."""
    if message.document.file_name.endswith(".pdf"):
        file_id = message.document.file_id
        file = await client.download_media(file_id)
        
        # Initialize empty text variable
        pdf_text = ""
        page_texts = []

        try:
            # First, try extracting text directly from PDF (for text-based PDFs)
            with open(file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text = page.extract_text() or ""
                    page_texts.append(text)
                    pdf_text += text

            # Check if text is missing (indicating image-based content)
            if not pdf_text.strip():
                images = pdf2image.convert_from_path(file)
                for page_num, image in enumerate(images, start=1):
                    text = pytesseract.image_to_string(image)
                    
                    # Handle low-confidence text extraction
                    if len(text.strip()) < 50:
                        prompt_text = (
                            f"The text on page {page_num} is unclear or partially missing. "
                            "Provide an explanation in simple, structured notes format."
                        )
                        response = genai.GenerativeModel(
                            model_name="gemini-pro",
                            generation_config={"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 800}
                        ).generate_content([prompt_text])
                        text += response.text
                    
                    page_texts.append(text)

            user_id = message.from_user.id
            user_pdfs[user_id] = page_texts
            await message.reply("PDF processed successfully. Select your topic to continue.")
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
    """Ask users to choose a topic, process relevant pages, and handle user questions."""
    user_id = message.from_user.id
    if user_id in user_pdfs:
        question = message.text.lower()
        page_texts = user_pdfs[user_id]
        
        # Find pages with relevant content for the specified topic
        selected_pages = [i for i, page in enumerate(page_texts, start=1) if any(keyword in page.lower() for keyword in question.split())]
        
        if not selected_pages:
            await message.reply("Couldn't find relevant pages. Try another question.")
            return
        
        # Limit to the first 10 relevant pages to optimize load
        relevant_text = "".join(page_texts[i - 1] for i in selected_pages[:10])
        prompt_text = f"• Main Topic\n  ✓ Key Points\n  ● Details\n  ○ Examples\n\n{relevant_text}\n\nQuestion: {question}"

        # Generate response using Gemini
        response = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config={
                "temperature": 1,
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": 1000
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ]
        ).generate_content([prompt_text])
        
        await client.send_message(
            chat_id=message.chat.id,
            text=response.text,
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
                    user_pdfs.pop(user_id, None)  # Clear any stored PDF data
                    await message.reply("New chat started. Ask me anything!")
                    return

                user_messages = user_conversations.get(user_id, [])
                user_messages.append(message.text)
                prompt = "\n".join(user_messages)

                response = genai.GenerativeModel(
                    model_name="gemini-pro",
                    generation_config={
                        "temperature": 1,
                        "top_p": 1,
                        "top_k": 1,
                        "max_output_tokens": 1000
                    },
                    safety_settings=[
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                    ]
                ).generate_content([prompt])

                users = await full_userbase()
                footer_credit = "<b>ADMIN ID:</b> - @talktomembbs_bot\n<b>Total Users:</b> {}".format(len(users))

                await client.send_message(
                    chat_id=message.chat.id,
                    text=f"{response.text}\n{footer_credit}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=inline_button
                )

                user_conversations[user_id] = user_messages
            except Exception as error:
                print(error)
    else:
        return

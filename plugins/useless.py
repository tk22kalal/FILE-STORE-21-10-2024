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
from nltk.tokenize import sent_tokenize

genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")

buttonz = ReplyKeyboardMarkup(
    [
        ["newchat⚡️"],
    ],
    resize_keyboard=True
)

inline_button = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🩺 MEDICAL LECTURES", url="https://sites.google.com/view/pavoladdder")]]
)

# Dictionary to store user/admin conversations and PDF content
user_conversations = {}
user_pdfs = {}

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

@Client.on_message(filters.document.mime_type("application/pdf"))
async def pdf_handler(client: Client, message: Message):
    file_id = message.document.file_id
    file = await client.download_media(file_id)
    
    # Extract text from the PDF
    with open(file, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        pdf_text = ""
        for page in reader.pages:
            pdf_text += page.extract_text()
    
    user_id = message.from_user.id
    user_pdfs[user_id] = pdf_text
    await message.reply("PDF found. Reply to this PDF with your question to ask questions related to its content.")

@Client.on_message(filters.reply & filters.text & filters.private)
async def pdf_question_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_pdfs:
        question = message.text
        pdf_content = user_pdfs[user_id]
        
        # Create chunks from the PDF text
        sentences = sent_tokenize(pdf_content)
        chunks = [" ".join(sentences[i:i + 5]) for i in range(0, len(sentences), 5)]
        
        # Find relevant chunks based on keywords
        relevant_chunks = [chunk for chunk in chunks if any(keyword.lower() in chunk.lower() for keyword in question.split())]
        prompt_text = " ".join(relevant_chunks)
        
        # Set up the model
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
        
        # Generate response using Gemini model
        response = model.generate_content([prompt_text + "\n\nQuestion: " + question])
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
    if AI:
        user_id = message.from_user.id
        if user_id:
            try:
                if message.text.lower().strip() == "/newchat" or message.text.strip() == 'newchat⚡️':
                    user_conversations.pop(user_id, None)
                    user_pdfs.pop(user_id, None)  # Clear any stored PDF data
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

from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from pyrogram.enums import ParseMode
from config import ADMINS, BOT_STATS_TEXT, USER_REPLY_TEXT, AI, OPENAI_API, AI_LOGS
from datetime import datetime
from helper_func import get_readable_time
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from pyrogram import Client, filters
import requests
import google.generativeai as genai
from database.database import full_userbase
import streamlit as st
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import google.generativeai as genai
from langchain.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from langchain.vectorstores import Chroma
from dotenv import load_dotenv

load_dotenv()
os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

genai.configure(api_key="AIzaSyBjcQWATZfQ9vwytmlWEuLPrgvntdixuk0")

buttonz = ReplyKeyboardMarkup(
    [
        ["newchat⚡️"],
    ],
    resize_keyboard=True
)

inline_button = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🩺 MEDICAL LECTURES", url="https://sites.google.com/view/pavoladdder")]]
)

def get_pdf_text(pdf_docs):
    text=""
    for pdf in pdf_docs:
        pdf_reader= PdfReader(pdf)
        for page in pdf_reader.pages:
            text+= page.extract_text()
    return  text



def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(text)
    return chunks

def get_vector_store(text_chunks):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vector_index = Chroma.from_texts(texts, embeddings).as_retriever()
    return vector_index



def get_conversational_chain():

    prompt_template = """
    Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
    provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
    Context:\n {context}?\n
    Question: \n{question}\n

    Answer:
    """

    model = ChatGoogleGenerativeAI(model="gemini-pro",
                             temperature=0.3)

    prompt = PromptTemplate(template = prompt_template, input_variables = ["context", "question"])
    chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)

    return chain



def user_input(user_question, vector_store, chain):
    embeddings = GoogleGenerativeAIEmbeddings(model = "models/embedding-001")
    docs = vector_store.get_relevant_documents(question)    
    response = chain({"input_documents": docs, "question": user_question}, return_only_outputs=True)
    return response.text


# Global variables for storing user conversations
user_conversations = {}
vector_store = None
@Client.on_message((filters.private & filters.text) | (filters.command("newchat") | filters.regex('newchat⚡️')))
async def lazy_answer(client: Client, message: Message):
    global vector_store
    if AI:
        user_id = message.from_user.id
        if user_id:
            try:
                # Check if user wants to start a new chat
                if message.text.lower().strip() == "/newchat" or message.text.strip() == 'newchat⚡️':
                    user_conversations.pop(user_id, None)  # Remove user's conversation history
                    response_text = "New chat started. Ask me anything!"
                    await message.reply(response_text)
                    return

                # If the user uploads a PDF
                if message.document:
                    pdf_docs = await message.document.download()
                    raw_text = get_pdf_text([pdf_docs])
                    text_chunks = get_text_chunks(raw_text)
                    vector_store = get_vector_store(text_chunks)
                    

                # Get the user's previous messages
                user_messages = user_conversations.get(user_id, [])
                user_messages.append(message.text)

                user_question = "\n".join(user_messages)
                if vector_store is not None:
                    embeddings = GoogleGenerativeAIEmbeddings(model = "models/embedding-001")
                    docs = vector_store.get_relevant_documents(question)    
                    response = chain({"input_documents": docs, "question": user_question}, return_only_outputs=True)
                    return response.text
                
                users = await full_userbase()
                footer_credit = "<b>ADMIN ID:</b> - @talktomembbs_bot\n<b>Total Users:</b> {}".format(len(users))

                lazy_response = response.text

                await client.send_message(
                    AI_LOGS,
                    text=f"<b>Name - {message.from_user.mention}\n{user_id}\n</b>CONVERSATION HISTORY:-\n{prompt}\n</b>ANSWER:-\n{lazy_response}",
                    parse_mode=ParseMode.HTML
                )

                await client.send_message(chat_id=message.chat.id, text=f"{lazy_response}\n{footer_credit}", parse_mode=ParseMode.HTML, reply_markup=inline_button)

                # Update user conversation history
                user_conversations[user_id] = user_messages
            except Exception as error:
                print(error)
    else:
        return


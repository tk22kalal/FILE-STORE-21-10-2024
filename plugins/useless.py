from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from pyrogram.enums import ParseMode
from config import ADMINS, AI, OPENAI_API
from datetime import datetime
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client
import io
from google.cloud import vision
import google.generativeai as genai
from docx import Document
import pdf2image

# Configure Google Gemini API and Vision
genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/gen-lang-client-0707503202-21d07fd84f57.json")


@Client.on_message(filters.document)
async def pdf_handler(client: Client, message: Message):
    """Handle PDF uploads, extract text from PDF via OCR, format notes, and send as Word document."""
    if message.document.file_name.endswith(".pdf"):
        file_id = message.document.file_id
        file = await client.download_media(file_id)
        
        document = Document()
        pdf_text = ""

        try:
            # Convert each page to image and perform OCR
            images = pdf2image.convert_from_path(file, dpi=300)
            for page_num, image in enumerate(images):
                image_bytes = io.BytesIO()
                image.save(image_bytes, format='JPEG')
                vision_image = vision.Image(content=image_bytes.getvalue())
                
                ocr_response = vision_client.text_detection(image=vision_image)
                ocr_text = ocr_response.full_text_annotation.text
                pdf_text += f"Page {page_num + 1}:\n{ocr_text}\n\n"

            # Generate notes format using Gemini AI
            formatted_prompt = (
                "Convert the following content into a structured, easy-to-understand notes format "
                "with bullet points and clear sections. Use bold headings:\n\n" + pdf_text
            )
            model = genai.GenerativeModel(
                model_name="gemini-pro",
                generation_config={"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 3000}
            )
            response = model.generate_content([formatted_prompt])
            notes_text = response.text

            # Format notes and add to Word document
            parts = notes_text.split("\n")
            for part in parts:
                if part.startswith("●") or part.startswith("○") or part.startswith("✓"):
                    document.add_paragraph(part)
                elif "**" in part:  # Format headings with <b> tags
                    part = part.replace("**", "").strip()
                    document.add_heading(part, level=2)
                else:
                    document.add_paragraph(part)

            # Save Word document
            word_file = io.BytesIO()
            document.save(word_file)
            word_file.seek(0)

            await client.send_document(
                chat_id=message.chat.id,
                document=word_file,
                file_name="Notes.docx",
                caption="Here are your notes in Microsoft Word format."
            )

        except Exception as e:
            await message.reply("Error processing the PDF. Please try again.")
            print(f"Error processing PDF: {e}")
    else:
        await message.reply("Please upload a PDF document.")

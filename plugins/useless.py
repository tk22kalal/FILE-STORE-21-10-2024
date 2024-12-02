from bot import Bot
import openai
from pyrogram.types import Message
from pyrogram import filters
from pyrogram import Client
import io
from google.cloud import vision
import google.generativeai as genai
import pdf2image
import asyncio
import re
from groq import Groq
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF

# Configure Google Gemini API and Vision
openai.api_key = "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"
genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/gen-lang-client-0707503202-21d07fd84f57.json")

@Client.on_message(filters.document)
async def pdf_handler(client: Client, message: Message):
    """Handle PDF uploads, extract text via OCR, convert to handwritten-style PDF, and send it."""
    if message.document.file_name.endswith(".pdf"):
        # Send a temporary "Processing..." message
        processing_message = await client.send_message(chat_id=message.chat.id, text="Processing... 0%")

        file_id = message.document.file_id
        file = await client.download_media(file_id)

        try:
            # Convert each page to an image and perform OCR
            images = pdf2image.convert_from_path(file, dpi=300)
            total_pages = len(images)

            all_notes_text = ""

            for page_num, image in enumerate(images, start=1):
                # Update the progress percentage
                progress = int((page_num / total_pages) * 100)
                await processing_message.edit_text(f"Processing... {progress}%")

                # Process the current page
                image_bytes = io.BytesIO()
                image.save(image_bytes, format='JPEG')
                vision_image = vision.Image(content=image_bytes.getvalue())
                ocr_response = vision_client.text_detection(image=vision_image)
                ocr_text = ocr_response.full_text_annotation.text

                # Generate notes using Gemini API
                formatted_prompt = (
                    "Analyze and summarize the content into organized notes:\n\n"
                    + ocr_text
                )
                groq_client = Groq(api_key="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")

                # Generate the completion
                completion = groq_client.chat.completions.create(
                    model="llama-3.1-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are an expert assistant that structures and simplifies content and makes notes."},
                        {"role": "user", "content": formatted_prompt}
                    ]
                )
                if hasattr(completion, "choices"):
                    notes_text = completion.choices[0].message.content
                else:
                    raise ValueError("Unexpected response structure from Groq API.")

                all_notes_text += f"\n\nPage {page_num}:\n{notes_text}"

                # Rest between pages to avoid hitting API limits or overloading
                await asyncio.sleep(2)

            # Generate handwritten text images
            images = []
            font_path = "plugins/DancingScript-Variable.ttf"  # Replace with the path to your handwriting font
            font = ImageFont.truetype(font_path, size=24)

            for page_text in all_notes_text.split("\n\nPage"):
                if not page_text.strip():
                    continue

                image = Image.new("RGB", (1200, 1600), "white")
                draw = ImageDraw.Draw(image)

                # Split text into lines for wrapping
                lines = re.split(r'\n+', page_text)
                y_position = 50
                for line in lines:
                    draw.text((50, y_position), line, font=font, fill="black")
                    y_position += 50

                    if y_position > 1550:  # Start a new page if content overflows
                        images.append(image)
                        image = Image.new("RGB", (1200, 1600), "white")
                        draw = ImageDraw.Draw(image)
                        y_position = 50

                # Add the last page
                images.append(image)

            # Convert images to a PDF
            pdf_path = "notes.pdf"
            pdf = FPDF()
            for img in images:
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="JPEG")
                img_bytes.seek(0)

                pdf.add_page()
                pdf.image(img_bytes, x=0, y=0, w=210, h=297)  # A4 size scaling

            pdf.output(pdf_path)

            # Send the PDF back to the user
            with open(pdf_path, "rb") as pdf_file:
                await client.send_document(
                    chat_id=message.chat.id,
                    document=pdf_file,
                    file_name="Handwritten_Notes.pdf",
                    caption="Here are your handwritten notes."
                )

            # Delete the temporary processing message
            await processing_message.delete()

        except Exception as e:
            await message.reply("Error processing the PDF. Please try again.")
            print(f"Error processing PDF: {e}")
            await processing_message.delete()

    else:
        await message.reply("Please upload a valid PDF document.")

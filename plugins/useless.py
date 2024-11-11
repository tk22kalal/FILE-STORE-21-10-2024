from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from pyrogram import Client
import io
from google.cloud import vision
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import pdf2image
import asyncio

# Configure Google Gemini API and Vision
genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/gen-lang-client-0707503202-21d07fd84f57.json")

@Client.on_message(filters.document)
async def pdf_handler(client: Client, message: Message):
    """Handle PDF uploads, extract text via OCR, convert to notes format, and send as a formatted Word document."""
    if message.document.file_name.endswith(".pdf"):
        # Send temporary "Processing..." message
        processing_message = await client.send_message(chat_id=message.chat.id, text="Processing...")

        file_id = message.document.file_id
        file = await client.download_media(file_id)
        
        document = Document()

        try:
            # Convert each page to image and perform OCR
            images = pdf2image.convert_from_path(file, dpi=300)
            for page_num, image in enumerate(images):
                image_bytes = io.BytesIO()
                image.save(image_bytes, format='JPEG')
                vision_image = vision.Image(content=image_bytes.getvalue())
                
                ocr_response = vision_client.text_detection(image=vision_image)
                ocr_text = ocr_response.full_text_annotation.text

                # Generate notes format using Gemini AI for the current page
                formatted_prompt = (
                    "Explain the following content in point-wise, easy language. Use ### for main headings, *** for headings, ## for subheadings, and * for normal paragraphs:\n\n" + ocr_text
                )
                model = genai.GenerativeModel(
                    model_name="gemini-pro"
                )
                response = model.generate_content([formatted_prompt])
                notes_text = response.text

                # Add notes text to Word document with specified formatting and minimal spacing
                lines = notes_text.split("\n")
                for line in lines:
                    if line.startswith("###"):
                        # Main Heading formatting
                        heading = document.add_paragraph()
                        run = heading.add_run(line.replace("###", "").strip())
                        run.font.bold = True
                        run.font.size = Pt(28)
                        run.font.name = 'Baskerville Old Face'
                        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

                    elif line.startswith("***"):
                        # H2 Heading formatting with numbered bullets
                        heading = document.add_paragraph(style='ListNumber')
                        run = heading.add_run(line.replace("***", "").strip())
                        run.font.bold = True
                        run.font.size = Pt(15)
                        run.font.name = 'Tahoma'
                        run.font.color.rgb = RGBColor(0, 128, 0)  # Green

                    elif line.startswith("##"):
                        # H3 Heading formatting with black circle bullets
                        heading = document.add_paragraph(style='ListBullet')
                        run = heading.add_run(line.replace("##", "").strip())
                        run.font.bold = True
                        run.font.size = Pt(15)
                        run.font.name = 'Tahoma'
                        run.font.color.rgb = RGBColor(255, 165, 0)  # Orange

                    elif line.startswith("*"):
                        # Normal Paragraph Text with hollow sphere bullets
                        paragraph = document.add_paragraph(style='ListBullet')
                        run = paragraph.add_run(line.replace("*", "").strip())
                        run.font.size = Pt(13)
                        run.font.name = 'Tahoma'

                    else:
                        paragraph = document.add_paragraph()
                        run = paragraph.add_run(line.strip())
                        run.font.size = Pt(13)
                        run.font.name = 'Tahoma'

                    # Set minimal spacing for all paragraphs
                    paragraph_format = paragraph.paragraph_format
                    paragraph_format.space_after = Pt(1)
                    paragraph_format.space_before = Pt(1)

                # Rest between pages to avoid hitting API limits or overloading
                await asyncio.sleep(2)

            # Save Word document
            word_file = io.BytesIO()
            document.save(word_file)
            word_file.seek(0)

            await client.send_document(
                chat_id=message.chat.id,
                document=word_file,
                file_name="Formatted_Notes.docx",
                caption="Here are your notes in a structured Microsoft Word format."
            )

            # Delete temporary processing message
            await client.delete_messages(chat_id=message.chat.id, message_ids=[processing_message.id])

        except Exception as e:
            await message.reply("Error processing the PDF. Please try again.")
            print(f"Error processing PDF: {e}")
            await client.delete_messages(chat_id=message.chat.id, message_ids=[processing_message.id])
    else:
        await message.reply("Please upload a PDF document.")

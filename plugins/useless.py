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
import re

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
                                # Generate notes format using Gemini AI for the current page
                formatted_prompt = (
                    "Explain the following content in point-wise, easy language with Main Title, Headings, Sub-headings, Points, Key Points, and Sub-Points. "
                    "Simplify Language, Organize in Point-Wise Format, Maintain Original Meaning, "
                    "Provide Clear Headings. Highlight Important words with bold in each line. "
                    "Use bulletins: Headings bulletins: number, Sub-heading bulletins: ★, Points bulletins: ●, Key-points bulletins: ⭘, Sub-Points bulletins: ◊. "
                    "Replace * and - with bulletins according to the above bulletin arrangement. Use ### for main title, *** for headings, ## for subheadings, "
                    "and - for normal paragraph key points:\n\n" + ocr_text
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
                        # Main Heading formatting with zero left indent
                        heading = document.add_paragraph()
                        heading_format = heading.paragraph_format
                        heading_format.left_indent = Pt(0)
                        heading_format.space_before = Pt(0)
                        heading_format.space_after = Pt(0)
                        run = heading.add_run(line.replace("###", "").strip())
                        run.font.bold = True
                        run.font.size = Pt(28)
                        run.font.name = 'Baskerville Old Face'
                        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

                    elif line.startswith("***"):
                        # H2 Heading formatting with slight indent
                        heading = document.add_paragraph(style='Heading 1')
                        heading_format = heading.paragraph_format
                        heading_format.left_indent = Pt(0)  # Slight indent
                        heading_format.space_before = Pt(0)
                        heading_format.space_after = Pt(0.5)
                        run = heading.add_run(line.replace("***", "").strip())
                        run.font.bold = True
                        run.font.size = Pt(15)
                        run.font.name = 'Tahoma'
                        run.font.color.rgb = RGBColor(0, 128, 0)  # Green

                    elif line.startswith("##"):
                        # H3 Subheading formatting with moderate indent
                        heading = document.add_paragraph(style='Heading 2')
                        heading_format = heading.paragraph_format
                        heading_format.left_indent = Pt(0)  # Moderate indent
                        heading_format.space_before = Pt(0)
                        heading_format.space_after = Pt(0.5)
                        run = heading.add_run(line.replace("##", "").strip())
                        run.font.bold = True
                        run.font.size = Pt(15)
                        run.font.name = 'Tahoma'
                        run.font.color.rgb = RGBColor(255, 165, 0)  # Orange

                    elif line.startswith("-"):
                        # Normal Paragraph Text
                        paragraph = document.add_paragraph(style='List Bullet')
                        paragraph_format = paragraph.paragraph_format
                        paragraph_format.left_indent = Pt(15)
                        paragraph_format.space_before = Pt(0)
                        paragraph_format.space_after = Pt(1)
                        run = paragraph.add_run(line.replace("-", "").strip())
                        run.font.size = Pt(13)
                        run.font.name = 'Tahoma'

                    else:
                        paragraph = document.add_paragraph()
                        paragraph_format = paragraph.paragraph_format
                        paragraph_format.left_indent = Pt(15)  # Further indent for non-marked text
                        paragraph_format.space_before = Pt(0)
                        paragraph_format.space_after = Pt(0.5)
                        run = paragraph.add_run(line.strip())
                        run.font.size = Pt(13)
                        run.font.name = 'Tahoma'

                # Rest between pages to avoid hitting API limits or overloading
                await asyncio.sleep(2)

            # Post-process document for **bold** text formatting
            for paragraph in document.paragraphs:
                # Find all occurrences of **bold text**
                parts = re.split(r'(\*\*[^*]+\*\*)', paragraph.text)
                paragraph.clear()
                for part in parts:
                    if part.startswith("**") and part.endswith("**"):
                        bold_text = part.replace("**", "")
                        run = paragraph.add_run(bold_text)
                        run.font.bold = True  # Strong bold
                    else:
                        run = paragraph.add_run(part)
                    run.font.size = Pt(13)
                    run.font.name = 'Tahoma'

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



# Configure Google Gemini API and Vision

from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from pyrogram import Client
import io
from google.cloud import vision
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
import pdf2image

genai.configure(api_key="AIzaSyCL_5XEd39cgAdcIBLhbu9OaT-RrhSSSjI")
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/gen-lang-client-0707503202-21d07fd84f57.json")


@Client.on_message(filters.document)
async def pdf_handler(client: Client, message: Message):
    """Handle PDF uploads, extract text via OCR, convert to notes format, and send as a formatted Word document."""
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
                "Convert the following content into a structured notes format with bullet points, "
                "using simple language. Organize into sections with headings and subheadings:\n\n" + pdf_text
            )
            model = genai.GenerativeModel(
                model_name="gemini-pro",
                generation_config={"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 3000}
            )
            response = model.generate_content([formatted_prompt])
            notes_text = response.text

            # Add notes text to Word document with specified formatting and minimal spacing
            lines = notes_text.split("\n")
            for line in lines:
                if line.startswith("MAIN:"):
                    # Main Heading formatting
                    heading = document.add_heading(level=1)
                    run = heading.add_run(line.replace("MAIN:", "").strip())
                    run.font.name = 'Baskerville Old Face'
                    run.font.size = Pt(28)
                    run.font.color.rgb = RGBColor(0, 0, 255)  # Blue
                    run.bold = True
                    heading.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                    heading.paragraph_format.space_after = Pt(0)
                    heading.paragraph_format.space_before = Pt(0)

                elif line.startswith("H2:"):
                    # H2 Heading formatting
                    heading = document.add_paragraph()
                    run = heading.add_run(line.replace("H2:", "").strip())
                    run.font.name = 'Tahoma'
                    run.font.size = Pt(15)
                    run.font.color.rgb = RGBColor(0, 128, 0)  # Green
                    run.bold = True
                    heading.style = 'List Bullet'
                    heading.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    heading.paragraph_format.space_after = Pt(0)
                    heading.paragraph_format.space_before = Pt(0)

                elif line.startswith("H3:"):
                    # H3 Heading formatting
                    heading = document.add_paragraph()
                    run = heading.add_run(line.replace("H3:", "").strip())
                    run.font.name = 'Tahoma'
                    run.font.size = Pt(15)
                    run.font.color.rgb = RGBColor(255, 165, 0)  # Orange
                    run.bold = True
                    heading.style = 'List Bullet 2'
                    heading.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    heading.paragraph_format.space_after = Pt(0)
                    heading.paragraph_format.space_before = Pt(0)

                elif line.startswith("H4:") or line.startswith("HIGHLIGHT:"):
                    # H4 Heading or highlighted word formatting
                    heading = document.add_paragraph()
                    run = heading.add_run(line.replace("H4:", "").replace("HIGHLIGHT:", "").strip())
                    run.font.name = 'Tahoma'
                    run.font.size = Pt(15)
                    run.font.color.rgb = RGBColor(0, 0, 0)  # Black
                    run.bold = True
                    heading.style = 'List Bullet 3'
                    heading.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    heading.paragraph_format.space_after = Pt(0)
                    heading.paragraph_format.space_before = Pt(0)

                else:
                    # Normal Paragraph Text
                    paragraph = document.add_paragraph(line.strip())
                    paragraph.style.font.size = Pt(13)
                    paragraph.style.font.name = 'Tahoma'
                    paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    paragraph.style = 'List Bullet' if line.strip() else 'Normal'
                    paragraph.paragraph_format.space_after = Pt(0)
                    paragraph.paragraph_format.space_before = Pt(0)

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

        except Exception as e:
            await message.reply("Error processing the PDF. Please try again.")
            print(f"Error processing PDF: {e}")
    else:
        await message.reply("Please upload a PDF document.")



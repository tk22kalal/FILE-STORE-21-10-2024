from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram import Client
import io
from google.cloud import vision
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import pdf2image

# Configure Google Gemini API and Vision
genai.configure(api_key="YOUR_GEMINI_API_KEY")
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/security_key.json")

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
                "Convert the following content into a structured point wise format with ms word bullet points, "
                "using simple language. Organize into sections with headings and subheadings:\n\n" + pdf_text
            )
            model = genai.GenerativeModel(
                model_name="gemini-pro",
                generation_config={"temperature": 0.8, "top_p": 1, "top_k": 1, "max_output_tokens": 3000}
            )
            response = model.generate_content([formatted_prompt])
            notes_text = response.text

            # Add notes text to Word document with structured formatting
            lines = notes_text.split("\n")
            for line in lines:
                if line.startswith("●") or line.startswith("○") or line.startswith("✓"):
                    paragraph = document.add_paragraph(line)
                    paragraph.style.font.size = Pt(12)
                    paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

                elif "**" in line:  # Headings
                    heading_text = line.replace("**", "").strip()
                    heading = document.add_heading(level=2)
                    run = heading.add_run(heading_text)
                    run.font.size = Pt(14)
                    run.font.color.rgb = RGBColor(0, 51, 102)  # Dark blue
                    run.bold = True

                elif "*" in line:  # Subheadings with bullets
                    subheading = document.add_paragraph(style="List Bullet")
                    subheading.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    run = subheading.add_run(line.replace("*", "").strip())
                    run.font.size = Pt(12)
                    run.font.color.rgb = RGBColor(51, 102, 0)  # Dark green
                    run.bold = True
                else:
                    # Regular text with bullets
                    paragraph = document.add_paragraph(line, style="List Bullet")
                    paragraph.style.font.size = Pt(12)
                    paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

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

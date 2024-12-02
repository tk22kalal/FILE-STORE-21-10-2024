import io
import os
import tempfile
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from google.cloud import vision
from groq import Groq
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
import pdf2image


# Google Vision and Groq AI configuration
vision_client = vision.ImageAnnotatorClient.from_service_account_file("plugins/gen-lang-client-0707503202-21d07fd84f57.json")
groq_client = Groq(api_key="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")


# Function to generate handwritten PDF on lined paper
def generate_handwritten_pdf_with_lines(text, font_path="plugins/LucidaHandwritingStdRg.TTF"):
    font_size = 24
    page_width, page_height = 1200, 1600
    margin = 50
    line_spacing = 50
    line_color = "lightblue"

    font = ImageFont.truetype(font_path, font_size)
    images = []

    # Split text into words for wrapping
    words = text.split()
    current_height = margin
    current_line = ""
    page = Image.new("RGB", (page_width, page_height), "white")
    draw = ImageDraw.Draw(page)

    # Draw lined paper background
    for y in range(margin, page_height - margin, line_spacing):
        draw.line([(margin, y), (page_width - margin, y)], fill=line_color, width=2)

    for word in words:
        # Test adding the next word to the current line
        test_line = f"{current_line} {word}".strip()
        text_width, _ = font.getsize(test_line)

        if text_width <= page_width - 2 * margin:
            current_line = test_line
        else:
            # Render the current line and reset
            draw.text((margin, current_height), current_line, font=font, fill="black")
            current_height += line_spacing

            # Start a new page if the content exceeds the page height
            if current_height + line_spacing > page_height - margin:
                images.append(page)
                page = Image.new("RGB", (page_width, page_height), "white")
                draw = ImageDraw.Draw(page)

                # Draw lines on the new page
                for y in range(margin, page_height - margin, line_spacing):
                    draw.line([(margin, y), (page_width - margin, y)], fill=line_color, width=2)

                current_height = margin

            current_line = word

    # Render the last line
    if current_line:
        draw.text((margin, current_height), current_line, font=font, fill="black")

    # Add the last page to the images list
    images.append(page)

    # Save images as a PDF
    pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    images[0].save(pdf_path, save_all=True, append_images=images[1:])
    return pdf_path


# Pyrogram handler for processing PDF files
@Client.on_message(filters.document)
async def pdf_handler(client: Client, message: Message):
    if not message.document.file_name.endswith(".pdf"):
        await message.reply("Please upload a valid PDF document.")
        return

    processing_message = await message.reply("Processing... 0%")

    # Download the PDF file
    pdf_file_path = await client.download_media(message.document.file_id)

    try:
        # Convert PDF to images
        images = pdf2image.convert_from_path(pdf_file_path, dpi=300)
        total_pages = len(images)

        all_notes_text = ""
        for page_num, image in enumerate(images, start=1):
            progress = int((page_num / total_pages) * 100)
            await processing_message.edit_text(f"Processing... {progress}%")

            # Convert image to bytes for OCR
            image_bytes = io.BytesIO()
            image.save(image_bytes, format="JPEG")

            # Perform OCR using Google Vision API
            vision_image = vision.Image(content=image_bytes.getvalue())
            ocr_response = vision_client.text_detection(image=vision_image)
            ocr_text = ocr_response.full_text_annotation.text

            # Generate structured notes using Groq AI
            formatted_prompt = f"Summarize and create notes for the following content:\n\n{ocr_text}"
            completion = groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert assistant that structures and simplifies content into notes."},
                    {"role": "user", "content": formatted_prompt}
                ]
            )

            if hasattr(completion, "choices"):
                notes_text = completion.choices[0].message.content
                all_notes_text += f"\n\nPage {page_num}:\n{notes_text}"
            else:
                raise ValueError("Unexpected response from Groq API.")

            await asyncio.sleep(1)  # Avoid rate-limiting issues

        # Generate handwritten-style PDF
        handwritten_pdf_path = generate_handwritten_pdf_with_lines(all_notes_text)

        # Send the handwritten PDF to the user
        await client.send_document(
            chat_id=message.chat.id,
            document=handwritten_pdf_path,
            file_name="Handwritten_Notes.pdf",
            caption="Here are your handwritten notes."
        )

    except Exception as e:
        await message.reply(f"An error occurred: {e}")
        print(f"Error processing PDF: {e}")

    finally:
        # Cleanup temporary files
        await processing_message.delete()
        if os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)
        if "handwritten_pdf_path" in locals() and os.path.exists(handwritten_pdf_path):
            os.remove(handwritten_pdf_path)

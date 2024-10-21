#(©)Codexbotz
import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot import Bot
from config import ADMINS
from helper_func import encode, get_message_id, decode, get_messages
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from config import ADMINS, FORCE_MSG, START_MSG, CUSTOM_CAPTION, DISABLE_CHANNEL_BUTTON, PROTECT_CONTENT, FCHANNEL_ID

@Bot.on_message(filters.private & filters.command('batch'))
async def batch(client: Client, message: Message):
    while True:
        try:
            # Prompt the user to provide the first message from the DB Channel
            first_message = await client.ask(
                text="Forward the First Message from DB Channel (with Quotes)..\n\nor Send the DB Channel Post Link",
                chat_id=message.from_user.id,
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60
            )
        except:
            return  # Return if there's an exception (e.g., timeout)

        # Get the message ID from the provided message or link
        f_msg_id = await get_message_id(client, first_message)

        if f_msg_id:
            break
        else:
            # Inform the user of an error if the message/link is not from the DB Channel
            await first_message.reply("❌ Error\n\nthis Forwarded Post is not from my DB Channel or this Link is taken from DB Channel", quote=True)
            continue

    while True:
        try:
            # Prompt the user to provide the last message from the DB Channel
            second_message = await client.ask(
                text="Forward the Last Message from DB Channel (with Quotes)..\nor Send the DB Channel Post link",
                chat_id=message.from_user.id,
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60
            )
        except:
            return  # Return if there's an exception (e.g., timeout)

        # Get the message ID from the provided message or link
        s_msg_id = await get_message_id(client, second_message)

        if s_msg_id:
            break
        else:
            # Inform the user of an error if the message/link is not from the DB Channel
            await second_message.reply("❌ Error\n\nthis Forwarded Post is not from my DB Channel or this Link is taken from DB Channel", quote=True)
            continue

    # Generate a list of links for each message between the first and second message
    message_links = []
    for msg_id in range(min(f_msg_id, s_msg_id), max(f_msg_id, s_msg_id) + 1):
        string = f"get-{msg_id * abs(client.db_channel.id)}"
        base64_string = await encode(string)
        link = f"https://t.me/{client.username}?start={base64_string}"
        message_links.append(link)

    for link in message_links:
        try:
            base64_string = link.split("=", 1)[1]
            decoded_string = await decode(base64_string)
        except Exception as e:
            print(f"Error decoding link: {e}")
            return

        argument = decoded_string.split("-")
        if len(argument) == 3:
            try:
                start = int(int(argument[1]) / abs(client.db_channel.id))
                end = int(int(argument[2]) / abs(client.db_channel.id))
            except:
                return
            if start <= end:
                ids = range(start, end + 1)
            else:
                ids = []
                i = start
                while True:
                    ids.append(i)
                    i -= 1
                    if i < end:
                        break
        elif len(argument) == 2:
            try:
                ids = [int(int(argument[1]) / abs(client.db_channel.id))]
            except:
                return

        try:
            messages = await get_messages(client, ids)
        except Exception as e:
            print(f"Error fetching messages: {e}")
            await message.reply_text("Something went wrong..!")
            return

        
        snt_msgs = []

        for msg in messages:

            if msg.video:
                # Forward only if it's a video
                if bool(CUSTOM_CAPTION) & bool(msg.document):
                    caption = CUSTOM_CAPTION.format(previouscaption="" if not msg.caption else msg.caption.html, filename=msg.document.file_name)
                else:
                    caption = "" if not msg.caption else msg.caption.html

                if DISABLE_CHANNEL_BUTTON:
                    reply_markup = msg.reply_markup
                else:
                    reply_markup = None

                try:
                    snt_msg = await msg.copy(chat_id=FCHANNEL_ID, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
                    try:
                        await asyncio.sleep(3)
                        snt_msgs.append(snt_msg)
                    except FloodWait as e:
                        await asyncio.sleep(e.x)
                        snt_msg = await msg.copy(chat_id=message.from_user.id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup,
                                      protect_content=PROTECT_CONTENT)
                        snt_msgs.append(snt_msg)
                    except Exception as e:
                        print(f"Error forwarding message: {e}")
                except Exception as e:
                    print(f"Error copying message: {e}")

      
    
@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command('genlink'))
async def link_generator(client: Client, message: Message):
    while True:
        try:
            channel_message = await client.ask(text = "Forward Message from the DB Channel (with Quotes)..\nor Send the DB Channel Post link", chat_id = message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except:
            return
        msg_id = await get_message_id(client, channel_message)
        if msg_id:
            break
        else:
            await channel_message.reply("❌ Error\n\nthis Forwarded Post is not from my DB Channel or this Link is not taken from DB Channel", quote = True)
            continue

    base64_string = await encode(f"get-{msg_id * abs(client.db_channel.id)}")
    link = f"https://t.me/{client.username}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')]])
    await channel_message.reply_text(f"<b>Here is your link</b>\n\n{link}", quote=True, reply_markup=reply_markup)





import os
import string
import random
import pytz
from datetime import date, datetime, timedelta
import requests as re

SHORTNER = os.environ.get("SHORTENER_SITE")
API = os.environ.get("SHORTENER_API")

async def get_shortlink(link):
    res = re.get(f'https://{SHORTNER}/api?api={API}&url={link}')
    res.raise_for_status()
    data = res.json()
    return data.get('shortenedUrl')

async def generate_random_string(num: int):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(num))
    return random_string

TOKENS = {}
VERIFIED = {}

async def check_token(bot, user_id, token):
    user = await bot.get_users(user_id)
    if user.id in TOKENS.keys():
        TKN = TOKENS[user.id]
        if token in TKN.keys():
            is_used = TKN[token]
            if is_used:
                return False
            else:
                return True
    else:
        return False

async def get_token(bot, user,k):
    user = await bot.get_users(user_id)
    token = await generate_random_string(7)
    TOKENS[user.id] = {token: False}
    link = f"{link}verify-{user.id}-{token}"
    shortened_verify_url = await get_shortlink(link)
    return str(shortened_verify_url)

async def verify_user(bot, user_id, token):
    user = await bot.get_users(user_id)
    
    # Calculate the expiration time (24 hours from the current time)
    tz = pytz.timezone('Asia/Kolkata')
    expiration_time = datetime.now(tz) + timedelta(hours=24)
    
    # Store the expiration time in the VERIFIED dictionary
    VERIFIED[user.id] = expiration_time

    # Return the Telegram bot URL
    return await generate_telegram_bot_url(bot_username)

async def check_verification(bot, user_id):
    user = await bot.get_users(user_id)
    current_time = datetime.now()

    if user.id in VERIFIED.keys():
        expiration_time = VERIFIED[user.id]

        if current_time < expiration_time:
            return True  # User is verified
        else:
            return False  # Verification has expired
    else:
        return False  # User is not verified


async def generate_telegram_bot_url(username):
    return f'tg://resolve?domain={username}&start=verified'

if __name__ == "__main__":
    # Replace 'bot_username' with your actual bot's username
    bot_username = "@FileXTera_bot"
    print("Bot URL:", generate_telegram_bot_url(bot_username))

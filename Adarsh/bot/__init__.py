# (c) NobiDeveloper
from pyrogram import Client
import pyromod.listen
from config import *
from os import getcwd
from ..vars import Var

StreamBot = Client(
    name='Web Streamer',
    api_id=APP_ID,
    api_hash=API_HASH,
    bot_token=TG_BOT_TOKEN,
    sleep_threshold=Var.SLEEP_THRESHOLD,
    workers=Var.WORKERS
)

multi_clients = {}
work_loads = {}

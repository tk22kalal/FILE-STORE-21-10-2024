#(©)Codexbotz

import os
import sys
import glob
import asyncio
import logging
import importlib.util
from pathlib import Path
from pyrogram import idle
from Adarsh.bot import StreamBot
from Adarsh.vars import Var
from aiohttp import web
from Adarsh.server import web_server
from Adarsh.utils.keepalive import ping_server
from Adarsh.bot.clients import initialize_clients
from config import CHANNEL_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)

ppath = "plugins/*.py"
files = glob.glob(ppath)
StreamBot.start()
loop = asyncio.get_event_loop()


async def start_services():
    print('\n')
    print('------------------- Initalizing Telegram Bot -------------------')
    bot_info = await StreamBot.get_me()
    StreamBot.username = bot_info.username
    print("------------------------------ DONE ------------------------------")
    print()
    print(
        "---------------------- Initializing Clients ----------------------"
    )
    await initialize_clients()
    print("------------------------------ DONE ------------------------------")
    print('\n')
    print('--------------------------- Importing ---------------------------')
    try:
        db_channel = await StreamBot.get_chat(CHANNEL_ID)
        StreamBot.db_channel = db_channel
        test = await StreamBot.send_message(chat_id=db_channel.id, text="TEST")
        await test.delete()
        print("Bot is admin in db channel")

    except Exception as e:
        # Handle the exception, log it, and optionally take other actions
        print(e)  # Print the error for debugging
        print(f"Make Sure bot is Admin in DB Channel, and Double check the CHANNEL_ID Value, Current Value {CHANNEL_ID}")
        print("\nBot Stopped bYE")
        sys.exit()
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = "plugins.{}".format(plugin_name)
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            print("Tech VJ Imported => " + plugin_name)
    if Var.ON_HEROKU:
        print("------------------ Starting Keep Alive Service ------------------")
        print()
        asyncio.create_task(ping_server())
    print('-------------------- Initalizing Web Server -------------------------')
    print('----------------------------- DONE ---------------------------------------------------------------------')
    print('\n')
    print('---------------------------------------------------------------------------------------------------------')
    print('---------------------------------------------------------------------------------------------------------')
    print(' follow me for more such exciting bots! https://github.com/NobiDeveloper')
    print('---------------------------------------------------------------------------------------------------------')
    print('\n')
    print('----------------------- Service Started -----------------------------------------------------------------')
    print('                        bot =>> {}'.format((await StreamBot.get_me()).first_name))
    print('                        server ip =>> {}:{}'.format(bind_address, Var.PORT))
    print('                        Owner =>> {}'.format((Var.OWNER_USERNAME)))
    if Var.ON_HEROKU:
        print('                        app runnng on =>> {}'.format(Var.FQDN))
    print('---------------------------------------------------------------------------------------------------------')
    print('Give a star to my repo https://github.com/NobiDeveloper/Nobita-Stream-Bot  also follow me for new bots')
    print('---------------------------------------------------------------------------------------------------------')
    await idle()

if __name__ == '__main__':
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        logging.info('----------------------- Service Stopped -----------------------')

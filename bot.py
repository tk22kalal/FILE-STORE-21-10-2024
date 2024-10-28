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
from config import CHANNEL_ID, FORCE_SUB_CHANNEL
import pytz
from datetime import date, datetime

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
    print('------------------- Initializing Telegram Bot -------------------')
    bot_info = await StreamBot.get_me()
    StreamBot.username = bot_info.username
    print("------------------------------ DONE ------------------------------")
    print()
    print("--------------- Initializing Clients ----------------")
    await initialize_clients()
    print("------------------------------ DONE ------------------------------")
    print('\n')
    print('--------------------------- Importing ---------------------------')
    
    # FORCE_SUB_CHANNEL check and setup
    if FORCE_SUB_CHANNEL:
        try:
            link = (await StreamBot.get_chat(FORCE_SUB_CHANNEL)).invite_link
            if not link:
                await StreamBot.export_chat_invite_link(FORCE_SUB_CHANNEL)
                link = (await StreamBot.get_chat(FORCE_SUB_CHANNEL)).invite_link
            StreamBot.invitelink = link
        except Exception as a:
            logging.warning(a)
            logging.warning("Bot can't Export Invite link from Force Sub Channel!")
            logging.warning(f"Please Double check the FORCE_SUB_CHANNEL value and Make sure Bot is Admin in channel with Invite Users via Link Permission, Current Force Sub Channel Value: {FORCE_SUB_CHANNEL}")
            logging.info("\nBot Stopped. Join https://t.me/CodeXBotzSupport for support")
            sys.exit()

    # Database channel check and setup
    try:
        db_channel = await StreamBot.get_chat(CHANNEL_ID)
        StreamBot.db_channel = db_channel
        test = await StreamBot.send_message(chat_id=db_channel.id, text="Test Message")
        await test.delete()
    except Exception as e:
        logging.warning(e)
        logging.warning(f"Make Sure bot is Admin in DB Channel, and Double check the CHANNEL_ID Value, Current Value {CHANNEL_ID}")
        logging.info("\nBot Stopped. Join https://t.me/CodeXBotzSupport for support")
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

    print('-------------------- Initializing Web Server -------------------------')
    me = await StreamBot.get_me()
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, Var.PORT).start()
    print('----------------------------- DONE ---------------------------------------------------------------------')
    print('\n')
    print('---------------------------------------------------------------------------------------------------------')
    print('---------------------------------------------------------------------------------------------------------')
    print('Follow me for more such exciting bots! https://github.com/NobiDeveloper')
    print('---------------------------------------------------------------------------------------------------------')
    print('\n')
    print('----------------------- Service Started -----------------------------------------------------------------')
    print('                        bot =>> {}'.format((await StreamBot.get_me()).first_name))
    print('                        server ip =>> {}:{}'.format(bind_address, Var.PORT))
    print('                        Owner =>> {}'.format((Var.OWNER_USERNAME)))
    if Var.ON_HEROKU:
        print('                        app running on =>> {}'.format(Var.FQDN))
    print('---------------------------------------------------------------------------------------------------------')
    print('Give a star to my repo https://github.com/NobiDeveloper/Nobita-Stream-Bot  also follow me for new bots')
    print('---------------------------------------------------------------------------------------------------------')
    await idle()

if __name__ == '__main__':
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        logging.info('----------------------- Service Stopped -----------------------')

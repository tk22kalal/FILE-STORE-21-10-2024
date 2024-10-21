from datetime import datetime

registration_date = datetime.now().date()
registration_time = datetime.now().strftime("%H:%M %p")  # Format time as HH:MM AM/PM

class script(object):
    LOG_TEXT_P = """#NewUser
ID - <code>{}</code>
Registration Time - <code>{}</code>
current_time - <code>{}</code>
Nᴀᴍᴇ - {}"""
    LOG_TEXT_G = """#NewGroup
Gʀᴏᴜᴘ = {}(<code>{}</code>)
Tᴏᴛᴀʟ Mᴇᴍʙᴇʀs = <code>{}</code>
Aᴅᴅᴇᴅ Bʏ - {}"""

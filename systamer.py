from pathlib import Path # todo dependencies?
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup # todo dependencies
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import nest_asyncio
import asyncio
import psutil # todo dependencies
from telegram.ext import Updater, CommandHandler
import pyautogui
from io import BytesIO
from PIL import Image

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot_token = ':'


# Directory where files will be saved
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")


async def send_screenshot(update, context):
    # Take a screenshot
    screenshot = pyautogui.screenshot()

    # Save the screenshot to a byte stream
    byte_io = BytesIO()
    screenshot.save(byte_io, 'PNG')
    byte_io.seek(0)

    # Send the screenshot back
    await update.message.reply_photo(photo=byte_io)

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    file = update.message.document
    if file:
        file_path = os.path.join(UPLOAD_DIR, file.file_name)
        await file.get_file().download(file_path)
        await update.message.reply_text(f"File '{file.file_name}' has been uploaded to '{UPLOAD_DIR}'.")
    else:
        await update.message.reply_text("No file was uploaded. Please try again.")


async def system_resource_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("system")
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')

    response = (
        f"CPU Usage: {cpu_usage}%\n"
        f"Memory Usage: {memory_info.percent}% ({memory_info.used / (1024 ** 3):.2f} GB used of {memory_info.total / (1024 ** 3):.2f} GB)\n"
        f"Disk Usage: {disk_usage.percent}% ({disk_usage.used / (1024 ** 3):.2f} GB used of {disk_usage.total / (1024 ** 3):.2f} GB)"
    )

    await update.message.reply_text(response)


async def list_processes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        processes.append(f"PID: {proc.info['pid']}, Name: {proc.info['name']}, "
                         f"CPU: {proc.info['cpu_percent']}%, Memory: {proc.info['memory_percent']}%")

    response = "\n".join(processes[:20])  # Limit to the first 20 processes for readability
    await update.message.reply_text(response)


async def kill_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        process_id = int(context.args[0])
        proc = psutil.Process(process_id)
        proc.terminate()
        await update.message.reply_text(f"Process {process_id} ({proc.name()}) terminated.")
    except (psutil.NoSuchProcess, IndexError, ValueError):
        await update.message.reply_text("Invalid process ID or process does not exist.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Send /browse to start navigating your file system.')


def list_files_and_directories(path: str):
    ITEMS_PER_PAGE = 10 # todo

    entries = os.listdir(path)
    buttons = []
    for entry in entries[:ITEMS_PER_PAGE]:  # Limit the number of entries per message
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            buttons.append(InlineKeyboardButton(entry + '/', callback_data=f"cd {full_path}"))
        else:
            buttons.append(InlineKeyboardButton(entry, callback_data=f"file {full_path}"))

    return buttons


async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    path = str(Path.home())  # Start from the home directory
    buttons = list_files_and_directories(path)

    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]  # Group buttons in rows
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Choose a directory or file:', reply_markup=reply_markup)


async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    command, path = query.data.split(' ', 1)

    if command == "cd":
        buttons = list_files_and_directories(path)
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=f'Navigating to: {path}', reply_markup=reply_markup)

    elif command == "file":
        with open(path, 'rb') as file:
            await query.message.reply_document(document=file)


async def main():
    # Build the application
    application = ApplicationBuilder().token(bot_token).build()

    # Register the handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("browse", browse))
    application.add_handler(CommandHandler("upload", handle_file_upload))
    application.add_handler(CommandHandler("system", system_resource_monitoring))
    application.add_handler(CommandHandler("processes", list_processes))
    application.add_handler(CommandHandler("kill", kill_process))
    application.add_handler(CommandHandler("screenshot", send_screenshot))

    application.add_handler(CallbackQueryHandler(handle_navigation))

    # Run the bot
    await application.run_polling()


if __name__ == '__main__':
    asyncio.run(main())


RESET = '\033[0m'
BOLD = '\033[1m'
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = "\033[1;33m"
BLUE = '\033[34m'
s = f"""
{GREEN}     _______.{RESET}____    ____  _______.{GREEN}___________.{RESET}    ___      .___  ___.  _______ .______      
{GREEN}    /       |{RESET}\   \  /   / /       {GREEN}|           |{RESET}   /   \     |   \/   | |   ____||   _  \     
{GREEN}   |   (----`{RESET} \   \/   / |   (----`{GREEN}---|  |----`{RESET}  /  ^  \    |  \  /  | |  |__   |  |_)  |    
{GREEN}    \   \    {RESET}  \_    _/   \   \    {GREEN}   |  |     {RESET} /  /_\  \   |  |\/|  | |   __|  |      /     
{GREEN}.----)   |   {RESET}    |  | .----)   |   {GREEN}   |  |     {RESET}/  _____  \  |  |  |  | |  |____ |  |\  \\
{GREEN}|_______/    {RESET}    |__| |_______/    {GREEN}   |__|    {RESET}/__/     \__\ |__|  |__| |_______|| _| \._\\
"""
print(s)

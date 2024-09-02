import time
from pathlib import Path # todo dependencies?
import os
import contextlib
from typing import NoReturn
import hashlib # todo dependencies?
import httpcore
import telegram.error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup # todo dependencies
from telegram import Update, Document, PhotoSize, Video, Audio, Voice, VideoNote
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import nest_asyncio # todo dependencies
import asyncio
import psutil # todo dependencies
from telegram.ext import CommandHandler
import pyautogui
from io import BytesIO

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot_token = ':'


# Directory where files will be saved
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")

BROWSE_PATH_DICT = dict()

async def send_screenshot(update, context):
    # Take a screenshot
    screenshot = pyautogui.screenshot()

    # Save the screenshot to a byte stream
    byte_io = BytesIO()
    screenshot.save(byte_io, 'PNG')
    byte_io.seek(0)

    # Send the screenshot back
    await update.message.reply_photo(photo=byte_io) # TODO wrapper for timeout here
    # TODO also set a timeout param here and for the rest of the msgs

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    # todo make a loop or smth
    if update.message.document:
        file = await update.message.document.get_file()
        file_path = os.path.join(UPLOAD_DIR, update.message.document.file_name)
        await file.download_to_drive(file_path)
        await update.message.reply_text(
            f"Document '{update.message.document.file_name}' has been uploaded to '{UPLOAD_DIR}'.")

    elif update.message.photo:
        photo = await update.message.photo[-1].get_file()  # Get the best quality photo
        file_path = os.path.join(UPLOAD_DIR, f"{photo.file_id}.jpg")
        await photo.download_to_drive(file_path)
        await update.message.reply_text(f"Photo has been uploaded to '{UPLOAD_DIR}' as '{photo.file_id}.jpg'.")

    elif update.message.video:
        video = await update.message.video.get_file()
        file_path = os.path.join(UPLOAD_DIR, f"{update.message.video.file_name or video.file_id}.mp4")
        await video.download_to_drive(file_path)
        await update.message.reply_text(
            f"Video has been uploaded to '{UPLOAD_DIR}' as '{update.message.video.file_name or video.file_id}.mp4'.")

    elif update.message.audio:
        audio = await update.message.audio.get_file()
        file_path = os.path.join(UPLOAD_DIR, f"{update.message.audio.file_name or audio.file_id}.mp3")
        await audio.download_to_drive(file_path)
        await update.message.reply_text(
            f"Audio file has been uploaded to '{UPLOAD_DIR}' as '{update.message.audio.file_name or audio.file_id}.mp3'.")

    elif update.message.voice:
        voice = await update.message.voice.get_file()
        file_path = os.path.join(UPLOAD_DIR, f"{voice.file_id}.ogg")
        await voice.download_to_drive(file_path)
        await update.message.reply_text(
            f"Voice message has been uploaded to '{UPLOAD_DIR}' as '{voice.file_id}.ogg'.")

    elif update.message.video_note:
        video_note = await update.message.video_note.get_file()
        file_path = os.path.join(UPLOAD_DIR, f"{video_note.file_id}.mp4")
        await video_note.download_to_drive(file_path)
        await update.message.reply_text(
            f"Video note has been uploaded to '{UPLOAD_DIR}' as '{video_note.file_id}.mp4'.")

    else:
        await update.message.reply_text("No file or media was uploaded. Please try again.")

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
    # todo for cmd in cmd list
    welcome_message = (
        "Welcome to the bot! Here are the commands you can use:\n\n"
        "/browse - Start navigating your file system.\n"
        "/upload - Upload a file to the server.\n"
        "/system - Get system resource usage.\n"
        "/processes - List running processes.\n"
        "/kill <PID> - Kill a process by its PID.\n"
        "/screenshot - Take a screenshot and send it.\n"
    )
    await update.message.reply_text(welcome_message)

async def upload_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # todo for cmd in cmd list
    upload_message = (
        f"Simply send a file, and it will be saved to -> {UPLOAD_DIR}"
    )
    await update.message.reply_text(upload_message)


def list_files_and_directories(path: str):
    entries = os.listdir(path)
    buttons = []
    BROWSE_PATH_DICT.clear()
    for entry in entries:  # Limit the number of entries per message
        full_path = os.path.join(path, entry)
        entry_hashed = hashlib.md5(full_path.encode()).hexdigest()
        BROWSE_PATH_DICT[entry_hashed] =  full_path # todo simplify remove above line
        if os.path.isdir(full_path):
            buttons.append(InlineKeyboardButton(entry + '/', callback_data=f"cd {entry_hashed}"))
        else:
            buttons.append(InlineKeyboardButton(entry, callback_data=f"file {entry_hashed}"))

    return buttons


async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    path = str(Path.home())  # Start from the home directory
    buttons = list_files_and_directories(path)

    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]  # Group buttons in rows
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Choose a directory or file:', reply_markup=reply_markup)


async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO if access is denied - send back a msg access is denied...
    query = update.callback_query
    command, hashed_path = query.data.split(' ', 1)
    path = BROWSE_PATH_DICT[hashed_path]  # todo if does not exist - exc?

    if command == "cd":
        buttons = list_files_and_directories(path)
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=f'Navigating to: {path}', reply_markup=reply_markup)

    elif command == "file":
        with open(path, 'rb') as file:
            await query.message.reply_document(document=file)


async def main() -> None:
    # Build the application
    application = ApplicationBuilder().token(bot_token).build()

    # Register the handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("browse", browse))
    application.add_handler(CommandHandler("system", system_resource_monitoring))
    application.add_handler(CommandHandler("processes", list_processes))
    application.add_handler(CommandHandler("kill", kill_process))
    application.add_handler(CommandHandler("screenshot", send_screenshot))

    application.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
    application.add_handler(MessageHandler(filters.PHOTO, handle_file_upload))
    application.add_handler(MessageHandler(filters.VIDEO, handle_file_upload))
    application.add_handler(MessageHandler(filters.AUDIO, handle_file_upload))
    application.add_handler(MessageHandler(filters.VOICE, handle_file_upload))
    application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_file_upload))
    application.add_handler(CommandHandler("upload", upload_info)) # todo needed? or simply add description in this cmd



    application.add_handler(CallbackQueryHandler(handle_navigation))

    # Run the bot
    try:
        print("Initializing application...")
        await application.initialize()
        print("Starting application...")
        await application.start()
        print("Starting updater polling...")
        await application.updater.start_polling()
        await asyncio.Event().wait()
    except KeyboardInterrupt: # todo verify if needed
        print("Stopping updater polling...")
        await application.updater.stop()
        print("Stopping application...")
        await application.stop()
    except telegram.error.InvalidToken:
        print("bad token")
    except httpcore.ConnectTimeout:
        print("timeout - check connection")
    finally:
        print("Shutting down application...")
        await application.shutdown()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())



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

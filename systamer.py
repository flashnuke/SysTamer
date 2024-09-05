import json
import time
from pathlib import Path # todo dependencies?
import os
import contextlib
from typing import NoReturn, Dict, Any, Callable
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

PASSWORD = "mypassword"  # Set your password here

# TODO challenge - if you can find the pass let me know (via commands, etc...)
# TODO cmd delete chat and - yes
# TODO cmd delete uploads - or not
# TODO cmd "ls" uploads - or not

def load_config(conf_path: str) -> Dict[str, Any]:
    """Loads a JSON file and returns the data as a dictionary."""
    try:
        with open(conf_path, 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"Config path not found -> {conf_path}")
    except json.JSONDecodeError:
        print(f"Error decoding config -> {conf_path}.") # todo handle errors etc in a more controlled manner



class SysTamer:
    def require_authentication(func):
        async def _impl(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if context.user_data.get("authenticated", False):
                # User is authenticated, proceed with the function
                return await func(self, update, context, *args, **kwargs)
            else:
                # User is not authenticated, prompt for password
                await update.message.reply_text("please login /login <password>") # todo better msg

        return _impl
    def __init__(self, json_conf: dict):
        self._bot_token = json_conf.get("bot_token", None)
        if not self._bot_token:  # todo export and handle in a config handler in a more generic manner
            raise Exception("asdasdasd")
        self._uploads_dir = os.path.join(os.getcwd(), "uploads")

        self._application: telegram.ext.Application = self._build_app()
        self._browse_path_dict = dict()

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Check if the user provided a password with the /login command
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a password. Usage: /login <password>")
            return

        user_password = context.args[0]  # Get the provided password

        # Check if the password is correct
        if user_password == PASSWORD:
            # Correct password, authenticate the user
            context.user_data["authenticated"] = True
            await update.message.reply_text("Password accepted! You are now authenticated.")
        else:
            # Incorrect password
            await update.message.reply_text("Incorrect password, please try again.")

    @require_authentication
    async def send_screenshot(self, update, context):
        # Take a screenshot
        screenshot = pyautogui.screenshot()

        # Save the screenshot to a byte stream
        byte_io = BytesIO()
        screenshot.save(byte_io, 'PNG')
        byte_io.seek(0)

        # Send the screenshot back
        await update.message.reply_photo(photo=byte_io, write_timeout=30) # todo handle timeout exc? reply timeout to user

    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # todo config path cannot be sent - security
        if not self._authorized:  # todo wrapper for each handler
            return False
        if not os.path.exists(self._uploads_dir):
            os.makedirs(self._uploads_dir)

        if update.message.document:
            file = await update.message.document.get_file()
            filename = update.message.document.file_name
            file_path = os.path.join(self._uploads_dir, filename)
            await file.download_to_drive(file_path)
            await update.message.reply_text(f"Document has been uploaded to '{self._uploads_dir}' as '{filename}'.")

        elif update.message.photo:
            photo = await update.message.photo[-1].get_file()  # Get the best quality photo
            filename = f"{photo.file_id}.jpg"
            file_path = os.path.join(self._uploads_dir, filename)
            await photo.download_to_drive(file_path)
            await update.message.reply_text(f"Photo has been uploaded to '{self._uploads_dir}' as '{filename}'.")

        elif update.message.video:
            video = await update.message.video.get_file()
            filename = f"{update.message.video.file_name or video.file_id}.mp4"
            file_path = os.path.join(self._uploads_dir, filename)
            await video.download_to_drive(file_path)
            await update.message.reply_text(
                f"Video has been uploaded to '{self._uploads_dir}' as '{filename}'.")

        elif update.message.audio:
            audio = await update.message.audio.get_file()
            filename = f"{update.message.audio.file_name or audio.file_id}.mp3"
            file_path = os.path.join(self._uploads_dir, filename)
            await audio.download_to_drive(file_path)
            await update.message.reply_text(
                f"Audio file has been uploaded to '{self._uploads_dir}' as '{filename}'.")

        elif update.message.voice:
            voice = await update.message.voice.get_file()
            filename = f"{voice.file_id}.ogg"
            file_path = os.path.join(self._uploads_dir, filename)
            await voice.download_to_drive(file_path)
            await update.message.reply_text(
                f"Voice message has been uploaded to '{self._uploads_dir}' as '{filename}'.")

        elif update.message.video_note:
            video_note = await update.message.video_note.get_file()
            filename = f"{video_note.file_id}.mp4"
            file_path = os.path.join(self._uploads_dir, filename)
            await video_note.download_to_drive(file_path)
            await update.message.reply_text(
                f"Video note has been uploaded to '{self._uploads_dir}' as '{filename}'.")

        else:
            await update.message.reply_text("No file or media was uploaded. Please try again.")

    @staticmethod
    async def system_resource_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')

        response = (
            f"CPU Usage: {cpu_usage}%\n"
            f"Memory Usage: {memory_info.percent}% ({memory_info.used / (1024 ** 3):.2f} GB used of {memory_info.total / (1024 ** 3):.2f} GB)\n"
            f"Disk Usage: {disk_usage.percent}% ({disk_usage.used / (1024 ** 3):.2f} GB used of {disk_usage.total / (1024 ** 3):.2f} GB)"
        )

        await update.message.reply_text(response)

    @staticmethod
    async def list_processes(update: Update, context: ContextTypes.DEFAULT_TYPE):
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            processes.append(f"PID: {proc.info['pid']}, Name: {proc.info['name']}, "
                             f"CPU: {proc.info['cpu_percent']}%, Memory: {proc.info['memory_percent']}%")

        response = "\n".join(processes[:20])  # Limit to the first 20 processes for readability
        await update.message.reply_text(response)

    @staticmethod
    async def kill_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            process_id = int(context.args[0])
            proc = psutil.Process(process_id)
            proc.terminate()
            await update.message.reply_text(f"Process {process_id} ({proc.name()}) terminated.")
        except (psutil.NoSuchProcess, IndexError, ValueError):
            await update.message.reply_text("Invalid process ID or process does not exist.")

    @staticmethod
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

    async def upload_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # todo for cmd in cmd list
        upload_message = (
            f"Simply send a file, and it will be saved to -> {self._uploads_dir}"
        )
        await update.message.reply_text(upload_message)

    def list_files_and_directories(self, path: str):
        entries = os.listdir(path)
        buttons = []
        self._browse_path_dict.clear()
        for entry in entries:  # Limit the number of entries per message
            full_path = os.path.join(path, entry)
            entry_hashed = hashlib.md5(full_path.encode()).hexdigest()
            self._browse_path_dict[entry_hashed] = full_path  # todo simplify remove above line
            if os.path.isdir(full_path):
                buttons.append(InlineKeyboardButton(entry + '/', callback_data=f"cd {entry_hashed}"))
            else:
                buttons.append(InlineKeyboardButton(entry, callback_data=f"file {entry_hashed}"))

        return buttons

    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        path = str(Path.home())  # Start from the home directory
        buttons = self.list_files_and_directories(path)

        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]  # Group buttons in rows
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text('Choose a directory or file:', reply_markup=reply_markup)

    async def handle_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # TODO if access is denied - send back a msg access is denied...
        query = update.callback_query
        command, hashed_path = query.data.split(' ', 1)
        path = self._browse_path_dict[hashed_path]  # todo if does not exist - exc?

        if command == "cd": # todo not hardcoded?
            buttons = self.list_files_and_directories(path)
            keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text=f'Navigating to: {path}', reply_markup=reply_markup)

        elif command == "file":
            with open(path, 'rb') as file:
                await query.message.reply_document(document=file)

    def _register_command_handlers(self, application: telegram.ext.Application) -> None:
        application.add_handler(CommandHandler("start", self.start))  # todo int
        application.add_handler(CommandHandler("browse", self.browse))
        application.add_handler(CommandHandler("system", self.system_resource_monitoring))
        application.add_handler(CommandHandler("processes", self.list_processes))
        application.add_handler(CommandHandler("kill", self.kill_process))
        application.add_handler(CommandHandler("screenshot", self.send_screenshot))
        application.add_handler(CommandHandler("upload", self.upload_info))
        application.add_handler(CommandHandler("login", self.login))

    def _register_message_handlers(self, application: telegram.ext.Application) -> None:
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_file_upload))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_file_upload))
        application.add_handler(MessageHandler(filters.VIDEO, self.handle_file_upload))
        application.add_handler(MessageHandler(filters.AUDIO, self.handle_file_upload))
        application.add_handler(MessageHandler(filters.VOICE, self.handle_file_upload))
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, self.handle_file_upload))

    def _register_cb_query_handlers(self, application: telegram.ext.Application) -> None:
        application.add_handler(CallbackQueryHandler(self.handle_navigation))

    def _build_app(self) -> telegram.ext.Application:
        application = ApplicationBuilder().token(self._bot_token).build()
        self._register_command_handlers(application)
        self._register_message_handlers(application)
        self._register_cb_query_handlers(application)

        return application

    async def run_forever(self) -> NoReturn:
        try: # todo print info errors etc
            print("Initializing application...")
            await self._application.initialize()
            print("Starting application...")
            await self._application.start()
            print("Starting updater polling...")
            await self._application.updater.start_polling()
            await asyncio.Event().wait()
        except KeyboardInterrupt:  # todo verify if needed
            print("Stopping updater polling...")
            await self._application.updater.stop()
            print("Stopping application...")
            await self._application.stop()
        except telegram.error.InvalidToken:
            print("bad token")
        except httpcore.ConnectTimeout:
            print("timeout - check connection")
        finally:
            print("Shutting down application...")
            await self._application.shutdown()


async def main() -> NoReturn:
    conf = load_config("config.json")
    tamer = SysTamer(conf)
    await tamer.run_forever()


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

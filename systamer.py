import os
import json
import psutil
import hashlib
import asyncio
import httpcore
import pyautogui
import nest_asyncio
import telegram.error

try:
    from .misc import *
except ImportError:
    from misc import *

from io import BytesIO
from pathlib import Path
from typing import NoReturn, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

nest_asyncio.apply()

PASSWORD = "mypassword"  # Set your password here

# TODO challenge - if you can find the pass let me know (via commands, etc...)
# TODO cmd delete chat and - yes
# TODO cmd delete uploads - or not
# TODO cmd "ls" uploads - or not


def load_config(conf_path: str) -> Dict[str, Any]:
    try:
        with open(conf_path, 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print_error(f"Config path not found -> {conf_path}")  # todo throw here
    except json.JSONDecodeError:
        print_error(f"Error decoding config -> {conf_path}.")  # todo handle errors etc in a more controlled manner

class SysTamer:
    _SENSITIVE_FILES = ["config.json"]

    def require_authentication(func, *args, **kwargs):
        async def _impl(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if context.user_data.get("authenticated", False):
                # User is authenticated, proceed with the function
                return await func(self, update, context, *args, **kwargs)
            else:
                # User is not authenticated, prompt for password
                await update.message.reply_text("please login /login <password>") # todo better msg

        return _impl

    @staticmethod
    async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=update.effective_message.message_id
            )
        except telegram.error.BadRequest as e:
            print(f"Error deleting message: {e}")

    def check_for_permission(func, *args, **kwargs):
        async def _impl(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                return await func(self, update, context, *args, **kwargs)
            except PermissionError:
                if update.effective_message:
                    await update.effective_message.reply_text("permission error")  # todo better msg
                if update.callback_query:  # todo export this outside and use for login as well?
                    await SysTamer.delete_message(update, context)
        return _impl

    def __init__(self, json_conf: dict):
        self._bot_token = json_conf.get("bot_token", None)
        if not self._bot_token:  # todo export and handle in a config handler in a more generic manner
            raise Exception("asdasdasd")
        self._uploads_dir = os.path.join(os.getcwd(), "uploads")

        self._application: telegram.ext.Application = self._build_app()
        self._browse_path_dict = dict()

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # todo remove msg with pass after
        # Check if the user provided a password with the /login command
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a password. Usage: /login <password>")
            return

        user_password = context.args[0]  # Get the provided password

        # Delete the message containing the password
        try: # todo refactor outside
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
        except telegram.error.BadRequest as e:
            print(f"Error deleting message: {e}")

        # Check if the password is correct
        if user_password == PASSWORD:
            # Correct password, authenticate the user
            context.user_data["authenticated"] = True
            await update.message.reply_text("Password accepted! You are now authenticated.")
        else:
            # Incorrect password
            await update.message.reply_text("Incorrect password, please try again.")

    async def logout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get("authenticated", False):
            self.deauthenticate(context)
        else:
            # User is not authenticated
            await update.message.reply_text("not logged in")  # todo better msg

    def deauthenticate(self, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["authenticated"] = False

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
        args_lower = [i.lower() for i in context.args]
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            if len(context.args) > 0:
                # filter provided - and proc is not in list (using any() to check for substr)
                filter_name = any(s in proc.info['name'].lower() for s in args_lower if proc.info['name'])
                filter_pid = any(s in str(proc.info['pid']) for s in args_lower)
                if not (filter_name or filter_pid):
                    continue
            processes.append(f"PID: {proc.info['pid']}, Name: {proc.info['name']}, "
                             f"CPU: {proc.info['cpu_percent']}%, Mem: {round(proc.info['memory_percent'], 1)}%")

        if len(processes) == 0:
            output = "no processes found"
            if len(context.args) > 0:
                output += f", filters: {context.args}"
            await update.message.reply_text(output)
        else:
            response_lst = list()
            for proc in processes:
                response_lst.append(proc)
                if len(response_lst) > 20:
                    await update.message.reply_text("\n".join(response_lst))
                    response_lst.clear()

            if len(response_lst) > 0:
                await update.message.reply_text("\n".join(response_lst))

    @staticmethod
    async def kill_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
        process_ids = [int(i) for i in context.args]
        for process_id in process_ids:
            try:
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
            "/processes - List running processes.\n" # todo u can filter
            "/kill <PID> - Kill a process by its PID.\n"
            "/screenshot - Take a screenshot and send it.\n"
            "/login <PASSWORD> - authenticate the session.\n"
            "/logout - de-authenticate the session.\n"
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

        # Add "Back" button to navigate to the parent directory if not at the root
        if path != str(Path.home()):  # If we are not in the home directory
            parent_directory = os.path.dirname(path)  # Get parent directory
            if os.path.isdir(parent_directory):  # Ensure the parent directory is valid
                parent_hashed = hashlib.md5(parent_directory.encode()).hexdigest()
                self._browse_path_dict[parent_hashed] = parent_directory
                buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"cd {parent_hashed}"))
        buttons.append(InlineKeyboardButton("❌️ Close", callback_data=f"action close"))  # todo where is it located? bottom or top

        for entry in entries:
            full_path = os.path.join(path, entry)
            entry_hashed = hashlib.md5(full_path.encode()).hexdigest()
            self._browse_path_dict[entry_hashed] = full_path

            # Ensure that it's a directory or file and not something like NTUSER.DAT
            if os.path.isdir(full_path):
                buttons.append(InlineKeyboardButton(entry + '/', callback_data=f"cd {entry_hashed}"))
            else:
                buttons.append(InlineKeyboardButton(entry, callback_data=f"file {entry_hashed}"))

        return buttons

    @check_for_permission
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        path = str(Path.home())  # Start from the home directory
        buttons = self.list_files_and_directories(path)
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]  # Group buttons in rows
        reply_markup = InlineKeyboardMarkup(keyboard)
        # todo add a "back" button here as well to close menu
        # todo handke telegram.error.NetworkError: httpx.ConnectError: [Errno 11001] getaddrinfo failed
        # todo of NetworkError happened at where exactly?
        await update.message.reply_text('Choose a directory or file:', reply_markup=reply_markup)


    @check_for_permission
    async def handle_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # TODO if access is denied - send back a msg access is denied...
        query = update.callback_query
        data = query.data.split(' ', 1)
        command = data[0]  # The command is the first part (e.g., "cd", "file", "action")

        if command == "cd":  # Handle directory navigation
            hashed_path = data[1]
            path = self._browse_path_dict.get(hashed_path)

            if path and os.path.isdir(path):  # Ensure the path is a valid directory
                buttons = self.list_files_and_directories(path)
                keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=f'Navigating to: {path}', reply_markup=reply_markup)
            else:
                await query.edit_message_text(text="The directory is invalid or does not exist.")

        elif command == "file":  # File clicked, show "Download/Delete/Back" options
            selected_file = self._browse_path_dict.get(data[1])
            parent_directory = os.path.dirname(selected_file)
            parent_hashed = hashlib.md5(parent_directory.encode()).hexdigest()

            # Store the parent directory in browse_path_dict
            self._browse_path_dict[parent_hashed] = parent_directory

            if selected_file and os.path.isfile(selected_file):  # Ensure it's a valid file
                context.user_data['selected_file'] = selected_file

                # Display action keypad
                keyboard = [
                    [InlineKeyboardButton("Download", callback_data="action download")],
                    [InlineKeyboardButton("Delete", callback_data="action delete")],
                    [InlineKeyboardButton("⬅️ Back", callback_data=f"cd {parent_hashed}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text="Choose an action:", reply_markup=reply_markup)
            else:
                await query.edit_message_text(text="The file is invalid or does not exist.")
                    # todo handle other errors here, Permission and general
        elif command == "action":  # Handle file actions (download or delete)
            action_type = data[1]  # This will be either 'download' or 'delete'
            selected_file = context.user_data.get('selected_file')

            if action_type == "download":
                if selected_file:
                    try:
                        with open(selected_file, 'rb') as file:
                            await query.message.reply_document(document=file)
                    except Exception as e:
                        await query.message.reply_text(f"Error: {str(e)}")

            elif action_type == "delete":
                if selected_file:
                    try:
                        os.remove(selected_file)
                        await query.edit_message_text(text=f"File '{selected_file}' has been deleted.")
                    except FileNotFoundError:
                        await query.edit_message_text(text=f"File '{selected_file}' not found.")
                    except Exception as e:
                        await query.edit_message_text(text=f"Error: {str(e)}")

            elif action_type == "close":
                await SysTamer.delete_message(update, context)
            else:
                await query.edit_message_text(text="Invalid action selected.")


    def _register_command_handlers(self, application: telegram.ext.Application) -> None:
        application.add_handler(CommandHandler("start", self.start))  # todo int
        application.add_handler(CommandHandler("browse", self.browse))
        application.add_handler(CommandHandler("system", self.system_resource_monitoring))
        application.add_handler(CommandHandler("processes", self.list_processes))
        application.add_handler(CommandHandler("kill", self.kill_process))
        application.add_handler(CommandHandler("screenshot", self.send_screenshot))
        application.add_handler(CommandHandler("upload", self.upload_info))
        application.add_handler(CommandHandler("login", self.login))
        application.add_handler(CommandHandler("logout", self.logout))

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
            try:
                print("Shutting down application...")
                await self._application.shutdown()
            except RuntimeError as exc:
                pass  # ignore 'RuntimeError: This Application is still running!'

async def main() -> NoReturn:
    conf = load_config("config.json")
    tamer = SysTamer(conf)
    await tamer.run_forever()


if __name__ == '__main__':
    invalidate_print()
    printf(f"\n{BANNER}\n"
           f"Written by {BOLD}@flashnuke{RESET}")
    printf(DELIM)
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        pass


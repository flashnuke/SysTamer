import psutil
import hashlib
import asyncio
import httpcore
import nest_asyncio
import telegram.error

try:
    from misc import *
except ImportError:
    from misc import *

import mss
from io import BytesIO
from PIL import Image

from telegram import Update
from telegram.ext import ContextTypes

async def send_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Take a screenshot using mss
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[0])  # Capture the full screen

        # Convert the screenshot to an Image object
        img = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)

        # Save the screenshot to a byte stream
        byte_io = BytesIO()
        img.save(byte_io, 'PNG')
        byte_io.seek(0)

        await self.reply_with_timeout(update, update.message.reply_photo, photo=byte_io)

from pathlib import Path
from typing import NoReturn, Any, Callable, Awaitable
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

nest_asyncio.apply()

PASSWORD = "mypassword"  # Set your password here

# TODO challenge - if you can find the pass let me know (via commands, etc...)
# TODO cmd delete chat and - yes
# TODO cmd delete uploads - or not
# TODO cmd "ls" uploads - or not
# TODO .browseignore - docs
# todo you can filter process by name - docs
# todo screenshot not supported on linux - tkinter... or find another way to do so

# todo add setup
# todo add empty config
# todo add x permissions on linux and shebang
# todo linux notes requirements NOTE: """You must install tkinter on Linux to use MouseInfo. Run the following: sudo apt-get install python3-tk python3-dev"""

class SysTamer:
    _BROWSE_IGNORE_PATH = ".browseignore"

    def require_authentication(func, *args, **kwargs):
        async def _impl(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if context.user_data.get("authenticated", False):
                # User is authenticated, proceed with the function
                return await func(self, update, context, *args, **kwargs)
            else:
                # User is not authenticated, prompt for password
                await update.message.reply_text("please login /login <password>")

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
                    await update.effective_message.reply_text("No permissions for this action, try running as superuser.")
                if update.callback_query:
                    await SysTamer.delete_message(update, context)
        return _impl

    def __init__(self, json_conf: dict):
        self._bot_token = json_conf.get("bot_token", None)
        if not self._bot_token:
            raise Exception("Bot token is missing")

        self._timeout_duration = json_conf.get("timeout_duration", 10)
        self._uploads_dir = os.path.join(os.getcwd(), "uploads")

        self._application: telegram.ext.Application = self._build_app()

        self._browse_path_dict = dict()
        self._ignored_paths = self.load_ignore_paths()

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Check if the user provided a password with the /login command
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a password. Usage: /login <password>")
            return

        user_password = context.args[0]  # Get the provided password

        # Delete the message containing the password
        await self.delete_message(update, context)

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
            await update.message.reply_text("Not logged in.")

    def deauthenticate(self, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["authenticated"] = False

    def load_ignore_paths(self) -> set:
        ignored_paths = set()
        try:
            with open(SysTamer._BROWSE_IGNORE_PATH, 'r') as file:
                for line in file:
                    line = line.strip()
                    if line:  # Ignore empty lines
                        # Add original path
                        ignored_paths.add(line)
                        # Convert to full absolute path and add to the set
                        full_path = str(Path(line).resolve())
                        ignored_paths.add(full_path)
        except FileNotFoundError:
            print_error(f"{SysTamer._BROWSE_IGNORE_PATH} was not loaded")
        return ignored_paths

    @require_authentication
    async def send_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Take a screenshot using mss
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])  # Capture the full screen

            # Convert the screenshot to an Image object
            img = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)

            # Save the screenshot to a byte stream
            byte_io = BytesIO()
            img.save(byte_io, 'PNG')
            byte_io.seek(0)

            await self.reply_with_timeout(update, update.message.reply_photo, photo=byte_io)

    async def reply_with_timeout(self, update: Update, async_reply_ptr: Callable[..., Awaitable[Any]], *args, **kwargs):
        try:
            await async_reply_ptr(*args, write_timeout=self._timeout_duration,
                                  connect_timeout=self._timeout_duration, read_timeout=self._timeout_duration, **kwargs)
        except telegram.error.TimedOut as exc:
            await update.message.reply_text(f"Request timed out after {self._timeout_duration} seconds.")
        except telegram.error.NetworkError as exc:
            await update.message.reply_text(f"Network error occurred: {exc}. Please try again later.")

    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def list_uploads(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not os.path.exists(self._uploads_dir):
                await update.message.reply_text("Upload directory does not exist.")
                return

            entries = os.listdir(self._uploads_dir)
            if not entries:
                await update.message.reply_text("Upload directory is empty.")
                return

            response_lines = []
            for index, entry in enumerate(entries, start=1):
                # Truncate the filename to 20 characters, including the extension
                name, ext = os.path.splitext(entry)
                max_name_length = 20 - len(ext)  # Calculate max length for the name part
                if len(entry) > 20:
                    if len(name) > max_name_length:
                        name = name[:max_name_length - 3] + '...'  # Truncate and add '...' if needed

                    entry = name + ext  # Reassemble the filename with the extension

                response_lines.append(f"**{index}**. {entry}")

            response_text = "\n".join(response_lines)
            await update.message.reply_text(response_text, parse_mode='Markdown')

        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}")

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
        welcome_message = "Welcome to the bot! Here are the commands you can use:\n\n"
        welcome_message += "\n".join([f"{cmd} - {desc}" for cmd, desc in COMMANDS_DICT.items()])
        await update.message.reply_text(welcome_message)

    async def upload_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        upload_message = (
            f"Simply send a file, and it will be saved to -> {self._uploads_dir}"
        )
        await update.message.reply_text(upload_message)

    def list_files_and_directories(self, path: str):
        entries = os.listdir(path)
        buttons = []
        self._browse_path_dict.clear()

        for entry in entries:
            full_path = os.path.join(path, entry)
            if full_path in self._ignored_paths or str(Path(full_path).resolve()) in self._ignored_paths:
                continue

            entry_hashed = hashlib.md5(full_path.encode()).hexdigest()
            self._browse_path_dict[entry_hashed] = full_path

            # Ensure that it's a directory or file and not something like NTUSER.DAT
            if os.path.isdir(full_path):
                buttons.append(InlineKeyboardButton(entry + '/', callback_data=f"cd {entry_hashed}"))
            else:
                buttons.append(InlineKeyboardButton(entry, callback_data=f"file {entry_hashed}"))

        # Add "Back" button to navigate to the parent directory if not at the root
        if path != str(Path.home()):  # If we are not in the home directory
            parent_directory = os.path.dirname(path)  # Get parent directory
            if os.path.isdir(parent_directory):  # Ensure the parent directory is valid
                parent_hashed = hashlib.md5(parent_directory.encode()).hexdigest()
                self._browse_path_dict[parent_hashed] = parent_directory
                buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"cd {parent_hashed}"))
        buttons.append(InlineKeyboardButton("❌️ Close", callback_data=f"action close"))
        return buttons


    @check_for_permission
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        path = str(Path.home())  # Start from the home directory
        buttons = self.list_files_and_directories(path)
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]  # Group buttons in rows
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Choose a directory or file:', reply_markup=reply_markup)

    @check_for_permission
    async def handle_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        elif command == "action":  # Handle file actions (download or delete)
            action_type = data[1]  # This will be either 'download' or 'delete'
            selected_file = context.user_data.get('selected_file')

            if action_type == "download":
                if selected_file:
                    try:
                        with open(selected_file, 'rb') as file:
                            await self.reply_with_timeout(update, query.message.reply_document, document=file)

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
        application.add_handler(CommandHandler("help", self.start))
        application.add_handler(CommandHandler("browse", self.browse))
        application.add_handler(CommandHandler("system", self.system_resource_monitoring))
        application.add_handler(CommandHandler("processes", self.list_processes))
        application.add_handler(CommandHandler("kill", self.kill_process))
        application.add_handler(CommandHandler("screenshot", self.send_screenshot))
        application.add_handler(CommandHandler("upload", self.upload_info))
        application.add_handler(CommandHandler("list_uploads", self.list_uploads))
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
        # TODO handle "telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running"
        # TODO ^ but where?
        try: # todo print info errors etc
            printf("Initializing application...")
            await self._application.initialize()
            printf("Starting application...")
            await self._application.start()
            printf("Starting updater polling...")
            await self._application.updater.start_polling()
            await asyncio.Event().wait()
        except KeyboardInterrupt:  # todo verify if needed
            printf("Stopping updater polling...")
            await self._application.updater.stop()
            printf("Stopping application...")
            await self._application.stop()
        except telegram.error.InvalidToken:
            printf("bad token")
        except httpcore.ConnectTimeout:
            printf("timeout - check connection")
        finally:
            try:
                printf("Shutting down application...")
                await self._application.shutdown()
            except RuntimeError as exc:
                pass  # ignore 'RuntimeError: This Application is still running!'

async def main() -> NoReturn:
    config_path = Path(__file__).resolve().parent / "config.json"
    printf(config_path)
    conf = load_config(config_path)
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


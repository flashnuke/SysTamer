#!/usr/bin/env python3

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

from pathlib import Path
from typing import NoReturn, Any, Callable, Awaitable
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

nest_asyncio.apply()


#   --------------------------------------------------------------------------------------------------------------------
#   ....................................................................................................................
#   .............._______.____    ____  _______.___________.    ___      .___  ___.  _______ .______....................
#   ............./       |\   \  /   / /       |           |   /   \     |   \/   | |   ____||   _  \...................
#   ............|   (----` \   \/   / |   (----`---|  |----`  /  ^  \    |  \  /  | |  |__   |  |_)  |..................
#   .............\   \      \_    _/   \   \       |  |      /  /_\  \   |  |\/|  | |   __|  |      /...................
#   ..........----)   |       |  | .----)   |      |  |     /  _____  \  |  |  |  | |  |____ |  |\  \...................
#   .........|_______/        |__| |_______/       |__|    /__/     \__\ |__|  |__| |_______|| _| \._\..................
#   ....................................................................................................................
#   Ⓒ by https://github.com/flashnuke Ⓒ................................................................................
#   --------------------------------------------------------------------------------------------------------------------

def require_authentication(func, *args, **kwargs):
    async def _impl(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if context.user_data.get("authenticated", False) or not SysTamer.should_authenticate():
            # User is authenticated, proceed with the function
            return await func(self, update, context, *args, **kwargs)
        else:
            # User is not authenticated, prompt for password
            await update.message.reply_text("please login via /login *<password\>*", parse_mode='MarkdownV2')

    return _impl


def log_action(func, *args, **kwargs):
    async def _impl(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        message_text = update.message.text  # This will contain the full command, e.g., "/start arg1 arg2"
        parts = message_text.split()
        command_name = parts[0] if parts else ""
        command_args = parts[1:] if len(parts) > 1 else []
        print_cmd(f"user {SysTamer.get_update_username(update)}\t|\tcmd {command_name}" +
                  (f"\t|\targs {','.join(command_args)}" if command_args else ''))
        return await func(self, update, context, *args, **kwargs)

    return _impl


class SysTamer:
    _BROWSE_IGNORE_PATH = ".browseignore"
    _PASSWORD = str()

    def __init__(self, json_conf: dict):
        self._bot_token = json_conf.get("bot_token", None)
        if self._bot_token:
            print_info(f"Bot token was set to -> {BOLD}{self._bot_token}{RESET}")
        else:
            raise Exception("Bot token is missing")

        SysTamer._PASSWORD = json_conf.get("password", str())
        if SysTamer._PASSWORD:
            print_info(f"Password set to -> {BOLD}{SysTamer._PASSWORD}{RESET}")
        else:
            print_info("No password was set, running an unauthenticated session...")

        self._timeout_duration = json_conf.get("timeout_duration", 10)
        self._uploads_dir = os.path.join(os.getcwd(), "uploads")

        self._application: telegram.ext.Application = self._build_app()

        self._browse_path_dict = dict()
        self._ignored_paths = SysTamer.load_ignore_paths()

    @staticmethod
    async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=update.effective_message.message_id
            )
        except telegram.error.BadRequest as e:
            print_error(f"Error deleting message: {e}")

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

    @staticmethod
    def get_update_username(update: Update) -> str:
        return update.effective_user.username if update.effective_user.username else update.effective_user.id

    @staticmethod
    def should_authenticate():
        return len(SysTamer._PASSWORD) > 0

    @staticmethod
    def load_ignore_paths() -> set:
        ignored_paths = set()
        try:
            with open(SysTamer._BROWSE_IGNORE_PATH, 'r') as file:
                for line in file:
                    line = line.strip()
                    if line:  # Ignore empty lines
                        ignored_paths.add(line)
                        full_path = str(Path(line).resolve())
                        ignored_paths.add(full_path)
        except FileNotFoundError:
            print_error(f"{SysTamer._BROWSE_IGNORE_PATH} was not loaded")
        print_info(f"Loaded `/browse` ignore paths from -> {BOLD}{SysTamer._BROWSE_IGNORE_PATH}{RESET}")
        return ignored_paths

    @log_action
    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.should_authenticate():
            await update.message.reply_text("Authentication is not required.")
            return

        # Check if the user provided a password with the /login command
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a password, usage: /login *<password\>*",
                                            parse_mode='MarkdownV2')
            return

        user_password = context.args[0]  # Get the provided password

        await self.delete_message(update, context)

        if user_password == SysTamer._PASSWORD:
            context.user_data["authenticated"] = True
            await update.message.reply_text("Password accepted! You are now authenticated.")
        else:
            await update.message.reply_text("Incorrect password, please try again.")

    @log_action
    async def logout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.should_authenticate():
            await update.message.reply_text("Cannot logout an authenticated session.")
            return
        if context.user_data.get("authenticated", False):
            self.deauthenticate(context)
            await update.message.reply_text("Logged out successfully.")
        else:
            # User is not authenticated
            await update.message.reply_text("Not logged in.")

    @staticmethod
    def deauthenticate(context: ContextTypes.DEFAULT_TYPE):
        context.user_data["authenticated"] = False

    @log_action
    @require_authentication
    async def send_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])  # Capture the full screen

            img = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)

            max_dimension = 4096
            if img.width > max_dimension or img.height > max_dimension:
                img.thumbnail((max_dimension, max_dimension))

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

    @require_authentication
    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not os.path.exists(self._uploads_dir):
            os.makedirs(self._uploads_dir)
        file_path = str()

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

        print_cmd(f"user {SysTamer.get_update_username(update)}\t|\tuploaded {file_path}")

    @log_action
    @require_authentication
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
            await update.message.reply_text(response_text, parse_mode='MarkdownV2')

        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}")

    @log_action
    @require_authentication
    async def system_resource_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')

        response = (
            f"CPU Usage: {cpu_usage}%\n"
            f"Memory Usage: {memory_info.percent}% ({memory_info.used / (1024 ** 3):.2f} GB used of {memory_info.total / (1024 ** 3):.2f} GB)\n"
            f"Disk Usage: {disk_usage.percent}% ({disk_usage.used / (1024 ** 3):.2f} GB used of {disk_usage.total / (1024 ** 3):.2f} GB)"
        )

        await update.message.reply_text(response)

    @log_action
    @require_authentication
    async def list_processes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        processes = []
        args_lower = [i.lower() for i in context.args]

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                proc_info = proc.as_dict(attrs=['pid', 'name', 'cpu_percent', 'memory_percent'])
                if len(context.args) > 0:
                    # filter provided - and proc is not in list (using any() to check for substr)
                    filter_name = any(s in proc_info['name'].lower() for s in args_lower if proc_info['name'])
                    filter_pid = any(s in str(proc_info['pid']) for s in args_lower)
                    if not (filter_name or filter_pid):
                        continue
                processes.append(proc_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        table_chunks = generate_proc_dict_msg(f"Processes:{len(processes)},Filters:{context.args if context.args else None}", processes)
        for chunk in table_chunks:
            await update.message.reply_text(f"```{chunk}```", parse_mode="MarkdownV2")

    @log_action
    @require_authentication
    async def kill_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        process_ids = [int(i) for i in context.args]
        if not process_ids:
            await update.message.reply_text("No PID provided, usage: /kill *<pid\>*", parse_mode="MarkdownV2")
            return
        for process_id in process_ids:
            try:
                proc = psutil.Process(process_id)
                proc.terminate()
                await update.message.reply_text(f"Process {process_id} ({proc.name()}) terminated.")
            except (psutil.NoSuchProcess, IndexError, ValueError):
                await update.message.reply_text("Invalid process ID or process does not exist.")

    @log_action
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_message = TG_BANNER + "\n\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n" \
                                      "by [@flashnuke](https://github.com/flashnuke/SysTamer)" \
                                      "\n\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"\
                          + generate_cmd_dict_msg("Commands", COMMANDS_DICT)
        await update.message.reply_text(welcome_message, parse_mode='MarkdownV2', disable_web_page_preview=True)

    @log_action
    @require_authentication
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

    @log_action
    @check_for_permission
    @require_authentication
    async def browse(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        path = str(Path.home())  # Start from the home directory
        buttons = self.list_files_and_directories(path)
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]  # Group buttons in rows
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Choose a directory or file:', reply_markup=reply_markup)

    @check_for_permission
    @require_authentication
    async def handle_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data.split(' ', 1)
        command = data[0]  # The command is the first part (e.g., "cd", "file", "action")
        print_cmd(f"user {SysTamer.get_update_username(update)}\t|\thandle_navigation received cmd -> {' '.join(data)}" + ('\t|\t(' + self._browse_path_dict.get(data[1]) + ')' if len(data) >= 1 and data[1] in self._browse_path_dict else ''))

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
                await self.delete_message(update, context)
            else:
                await query.edit_message_text(text="Invalid action selected.")

    def _register_command_handlers(self, application: telegram.ext.Application) -> None:
        application.add_handler(CommandHandler("start", self.start))
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

    def _error_handler(self, update: object, context: telegram.ext.CallbackContext):
        try:
            raise context.error
        except Exception as exc:
            print_error(f"Exception occurred: {exc}")

    async def run_forever(self) -> NoReturn:
        await self._application.updater.bot.set_my_commands([BotCommand(k, v) for k, v in COMMANDS_DICT.items()])

        try:
            print_info("Initializing application...")
            await self._application.initialize()
            await self._application.start()
            print_info("Starting updater polling...")
            await self._application.updater.start_polling(error_callback=self._error_handler)
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print_info("Stopping...")
            await self._application.updater.stop()
            await self._application.stop()
        except telegram.error.InvalidToken:
            print_error("bad token - make sure you set a correct bot token in `config.json`")
        except httpcore.ConnectTimeout:
            print_error("Connection timeout")
        finally:
            try:
                print_info("Shutting down...")
                await self._application.shutdown()
            except RuntimeError as exc:
                pass  # ignore 'RuntimeError: This Application is still running!'


async def main() -> NoReturn:
    config_path = Path(__file__).resolve().parent / "config.json"
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


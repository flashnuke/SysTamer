# SysTamer
![image](https://github.com/user-attachments/assets/34ea1223-1d90-4238-9536-a8cd74e964b9)

## Introduction

SysTamer is a Telegram bot that allows you to remotely monitor and control your system through Telegram messages. 
</br> With SysTamer, you can:

* Monitor system resources (CPU, memory, disk usage)
* List and manage running processes
* Capture and receive screenshots
* Browse and manage files on your system
* Upload files directly to your system via Telegram
* Secure access with authentication

## Requirements

* Python 3.7 or higher
* All the Python libraries that are listed in `requirements.txt`
* Telegram Bot API Token (obtain from BotFather)

### Obtaining a Telegram bot token
This is a one-time process that takes less than 1 minute. Start a chat with [@BotFather](https://core.telegram.org/bots/faq#how-do-i-create-a-bot) on telegram and obtain the bot token.
</br>
After obtaining the bot token and cloning the repository, set the token in the `config.json` file:

### Setting up `config.json`
```json
{
  "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
  "password": "YOUR_PASSWORD",
}
```
The initial config leaves the password field empty - meaning no authentication will be required.</br>
Otherwise, refer to the `/login <password>` command.

## Installation & Usage
```bash
git clone https://github.com/flashnuke/SysTamer.git
cd SysTamer
pip3 install -r requirements.txt # install requirements manually
python3 systamer.py
```

### Interact via Telegram
* Start: `/start` or `/help` to get the list of commands.
* Authenticate: `/login <password>` to authenticate yourself (if a password was [set up](https://github.com/flashnuke/SysTamer?tab=readme-ov-file#setting-up-configjson)).
* Use Commands: After authentication, you can use all available commands.

### Commands
| Command | Description |
|-------------------------|---------------|
| /start </br> /help      | Display the help message with available commands     |
| /login `<password> `    | Authenticate with the bot. Uses the password as set in `config.json`   |
| /logout                 | Logout from the bot     |
| /system                 | Get system resource usage (CPU, memory, disk)   |
| /processes `[filter]`   | List running processes. Optionally filter by process name or PID. </br> You can filter processes by name. For example: `/processes chrome`     |
| /kill `<pid>`           | Terminate a process by its PID   |
| /screenshot             | Capture and receive a screenshot of the system’s primary monitor     |
| /browse                 | Browse and manage files on the system (Paths under `.browseignore` will not be displayed)   |
| /upload                 | Instructions on how to upload files   |
| /list_uploads           | List files you’ve uploaded via Telegram   |


## Troubleshooting
* Conflict Errors: If you encounter telegram.error.Conflict, ensure only one instance of the bot is running (per token)
* Timeouts: If requests time out, check your internet connection or adjust the timeout_duration.
* Invalid Token: Double-check your Telegram Bot API token in the config.json file.
* Permissions: Run the script with appropriate permissions (sudo, administrator...) if you face PermissionError.

## Legal Disclaimer
This software is intended for personal use on your own systems. Unauthorized access to computer systems is illegal. The developers assume no liability and are not responsible for any misuse or damage caused by this program.

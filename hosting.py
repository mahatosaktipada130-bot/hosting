import os
import subprocess
import logging
import gc
import psutil
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#            FLASK WEB SERVER (Render Port)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot & Multi-Process Hosting Manager are running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port, use_reloader=False)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                  CONFIG & STORE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YAHAN_APNA_BOT_TOKEN_DALEIN")
HOST_DIR = "hosted_files"

# Running processes: {pid: {"file": filename, "path": file_path, "proc": process_obj}}
RUNNING_PROCESSES = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists(HOST_DIR):
    os.makedirs(HOST_DIR)

KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📋 Active Scripts"), KeyboardButton("📊 RAM Status")],
        [KeyboardButton("🛑 Stop All Scripts")]
    ],
    resize_keyboard=True
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#           MEMORY CLEANER SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def clear_memory():
    gc.collect()
    
    dead_pids = []
    for pid in list(RUNNING_PROCESSES.keys()):
        if not psutil.pid_exists(pid):
            dead_pids.append(pid)
    
    for pid in dead_pids:
        del RUNNING_PROCESSES[pid]

    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    logger.info(f"🧹 [AUTO-CLEANER] RAM Usage: {ram_mb:.2f} MB | Active Scripts: {len(RUNNING_PROCESSES)}")

async def background_ram_cleaner():
    while True:
        await asyncio.sleep(120)
        clear_memory()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                BOT HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Multi-Bot Hosting & Control Manager**\n\n"
        "📌 **Features:**\n"
        "• Apni file (`.py`, `.sh`) bhejein -> Auto-Run ho jayegi\n"
        "• **📋 Active Scripts** par click karke scripts **Stop** ya **Restart** karein\n"
        "• Script crash hone par aapko exact error log mil jayega!",
        parse_mode="Markdown",
        reply_markup=KEYBOARD
    )

async def monitor_script_output(proc, file_name, chat_id, context):
    """Background mein script ke logs monitor karega aur error aane par alert bhejega"""
    await asyncio.sleep(3) # Wait 3 sec to check if it immediately crashes
    
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode('utf-8') if proc.stderr else "Unknown error"
        error_msg = stderr[-1000:] if stderr else "No error log captured."
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ **Script Crash Alert!**\n\n📄 File: `{file_name}`\n❌ **Error Log:**\n```\n{error_msg}\n


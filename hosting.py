import os
import subprocess
import logging
import gc
import psutil
import asyncio
import threading
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#            FLASK WEB SERVER (Render Ke Liye)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot & Memory Cleaner are running live!"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YAHAN_APNA_BOT_TOKEN_DALEIN")
HOST_DIR = "hosted_files"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists(HOST_DIR):
    os.makedirs(HOST_DIR)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#           MEMORY CLEANER SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def clear_memory():
    """Unused memory aur RAM ko clean karta hai"""
    gc.collect()  # Python Garbage Collector
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    logger.info(f"🧹 [AUTO-CLEANER] Unused items cleared! Current RAM: {ram_mb:.2f} MB")

async def background_ram_cleaner():
    """Har 2 minute mein background mein unused memory clear karega"""
    while True:
        await asyncio.sleep(120)  # 120 seconds = 2 minutes
        clear_memory()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                BOT HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **File Hosting Bot**\n\n"
        "Apni file (`.py`, `.sh`) yahan bhejein.\n"
        "Bot ise save karke run kar dega!",
        parse_mode="Markdown"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document

    if not doc:
        await msg.reply_text("❌ Kripya ek valid file bhejein.")
        return

    file_name = doc.file_name
    file_path = os.path.join(HOST_DIR, file_name)

    await msg.reply_text(f"📥 Downloading `{file_name}`...", parse_mode="Markdown")
    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(file_path)

    await msg.reply_text(f"✅ File saved: `{file_name}`\n🚀 Running file now...", parse_mode="Markdown")

    try:
        if file_name.endswith(".py"):
            subprocess.Popen(["python3", file_path])
            await msg.reply_text(f"⚡ Python script `{file_name}` background mein run ho gayi hai!", parse_mode="Markdown")
        elif file_name.endswith(".sh"):
            os.chmod(file_path, 0o755)
            subprocess.Popen(["bash", file_path])
            await msg.reply_text(f"⚡ Shell script `{file_name}` background mein run ho gayi hai!", parse_mode="Markdown")
        else:
            await msg.reply_text("📁 File save ho gayi hai lekin auto-run unsupported extension par nahi hoga.")
    except Exception as e:
        await msg.reply_text(f"❌ Error while running file: `{str(e)}`", parse_mode="Markdown")
    
    # Task complete hone par immediate cleanup
    clear_memory()

async def post_init(application: Application):
    # Background Memory Cleaner Task Start Karein
    asyncio.create_task(background_ram_cleaner())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#         TELEGRAM BOT THREAD FOR GUNICORN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def run_telegram_bot():
    """Gunicorn ke andar background thread mein Telegram bot ko run karta hai"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Bot started with Memory Auto-Cleaner...")
    app.run_polling(drop_pending_updates=True)

# Gunicorn start hote hi bot thread run ho jayega
threading.Thread(target=run_telegram_bot, daemon=True).start()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                  LOCAL RUN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

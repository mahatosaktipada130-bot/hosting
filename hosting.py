import os
import subprocess
import logging
import gc
import psutil
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#            FLASK WEB SERVER (Render Port)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is active and running!"

def run_flask():
    """Flask app ko background thread mein chalata hai"""
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port, use_reloader=False)

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
    """Unused RAM clean karta hai"""
    gc.collect()
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    logger.info(f"🧹 [AUTO-CLEANER] RAM Usage: {ram_mb:.2f} MB")

async def background_ram_cleaner():
    """Har 2 minute mein RAM clear karega"""
    while True:
        await asyncio.sleep(120)
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
    
    clear_memory()

async def post_init(application: Application):
    asyncio.create_task(background_ram_cleaner())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                  MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    # 1. Web server ko background mein chalao
    Thread(target=run_flask, daemon=True).start()

    # 2. Bot ko Main Thread mein chalao (Isse set_wakeup_fd error fix ho jayega)
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Bot main thread mein start ho gaya hai...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()


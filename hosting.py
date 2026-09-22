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
    """Flask app ko background thread mein chalata hai"""
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port, use_reloader=False)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                  CONFIG & STORE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YAHAN_APNA_BOT_TOKEN_DALEIN")
HOST_DIR = "hosted_files"

# Running processes ko track karne ke liye dictionary: {pid: "filename.py"}
RUNNING_PROCESSES = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists(HOST_DIR):
    os.makedirs(HOST_DIR)

# Bottom Reply Keyboard Setup
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
    """Unused RAM clean karta hai aur dead processes ko list se hatata hai"""
    gc.collect()
    
    # Check Dead Processes
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
    """Har 2 minute mein RAM clear karega"""
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
        "• **📋 Active Scripts** par click karke ek-ek karke script stop karein\n"
        "• Direct buttons se saare hosted bots control karein",
        parse_mode="Markdown",
        reply_markup=KEYBOARD
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document

    if not doc:
        await msg.reply_text("❌ Kripya ek valid file bhejein.", reply_markup=KEYBOARD)
        return

    file_name = doc.file_name
    file_path = os.path.join(HOST_DIR, file_name)

    await msg.reply_text(f"📥 Downloading `{file_name}`...", parse_mode="Markdown")
    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(file_path)

    try:
        proc = None
        if file_name.endswith(".py"):
            proc = subprocess.Popen(["python3", file_path])
        elif file_name.endswith(".sh"):
            os.chmod(file_path, 0o755)
            proc = subprocess.Popen(["bash", file_path])
        else:
            await msg.reply_text("📁 File save ho gayi hai lekin auto-run unsupported extension par nahi hoga.", reply_markup=KEYBOARD)
            return

        if proc:
            RUNNING_PROCESSES[proc.pid] = file_name
            
            # Direct Stop Button along with File Success Message
            stop_btn = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🛑 Stop {file_name}", callback_data=f"stop_{proc.pid}")]
            ])

            await msg.reply_text(
                f"✅ **Script Running Successfully!**\n\n"
                f"📄 File: `{file_name}`\n"
                f"🆔 **PID:** `{proc.pid}`",
                parse_mode="Markdown",
                reply_markup=stop_btn
            )
    except Exception as e:
        await msg.reply_text(f"❌ Error while running file: `{str(e)}`", parse_mode="Markdown", reply_markup=KEYBOARD)
    
    clear_memory()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#         PROCESS CONTROL FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def list_processes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Har running script ke liye alag-alag Stop Inline Button dikhata hai"""
    clear_memory()
    if not RUNNING_PROCESSES:
        await update.message.reply_text("📭 Abhi koi bhi script run nahi ho rahi hai.", reply_markup=KEYBOARD)
        return

    text = "⚙️ **Active Running Scripts:**\nNiche kisi bhi script ke **Stop** button par click karke use band karein:\n"
    
    # Ek-ek karke button create karein har running file ke liye
    inline_buttons = []
    for pid, fname in RUNNING_PROCESSES.items():
        button_text = f"🛑 Stop {fname} (PID: {pid})"
        inline_buttons.append([InlineKeyboardButton(button_text, callback_data=f"stop_{pid}")])

    reply_inline_markup = InlineKeyboardMarkup(inline_buttons)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_inline_markup)

async def handle_inline_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline Stop Button ka click handle karta hai"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("stop_"):
        pid = int(data.split("_")[1])
        
        try:
            if pid in RUNNING_PROCESSES or psutil.pid_exists(pid):
                p = psutil.Process(pid)
                p.terminate()  # Process Stop
                file_name = RUNNING_PROCESSES.pop(pid, "Unknown File")
                await query.edit_message_text(f"🛑 Script `{file_name}` (PID: `{pid}`) ko stop kar diya gaya hai!", parse_mode="Markdown")
            else:
                await query.edit_message_text("❌ Yeh process pehle hi stop ho chuka hai.")
        except Exception as e:
            await query.edit_message_text(f"❌ Process stop karne mein error aaya: `{str(e)}`", parse_mode="Markdown")

    clear_memory()

async def stop_all_processes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saare running hosted scripts ko ek saath stop kar deta hai"""
    clear_memory()
    if not RUNNING_PROCESSES:
        await update.message.reply_text("📭 Koi running script nahi mili.", reply_markup=KEYBOARD)
        return

    count = 0
    for pid in list(RUNNING_PROCESSES.keys()):
        try:
            if psutil.pid_exists(pid):
                p = psutil.Process(pid)
                p.terminate()
            del RUNNING_PROCESSES[pid]
            count += 1
        except Exception:
            pass

    await update.message.reply_text(f"🛑 Saari `{count}` hosted scripts successfully stop kar di gayi hain!", parse_mode="Markdown", reply_markup=KEYBOARD)
    clear_memory()

async def ram_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Current RAM Status Check Karne Ke Liye"""
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    await update.message.reply_text(
        f"📊 **System Status:**\n\n"
        f"🧠 Main Bot RAM: `{ram_mb:.2f} MB`\n"
        f"⚡ Active Scripts: `{len(RUNNING_PROCESSES)}`",
        parse_mode="Markdown",
        reply_markup=KEYBOARD
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#         TEXT MESSAGE HANDLER (For Buttons)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📋 Active Scripts":
        await list_processes(update, context)
    elif text == "📊 RAM Status":
        await ram_status(update, context)
    elif text == "🛑 Stop All Scripts":
        await stop_all_processes(update, context)

async def post_init(application: Application):
    asyncio.create_task(background_ram_cleaner())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                  MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Commands & Callbacks
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_processes))
    app.add_handler(CommandHandler("stopall", stop_all_processes))
    app.add_handler(CommandHandler("ram", ram_status))
    
    # Button Callbacks & File Handlers
    app.add_handler(CallbackQueryHandler(handle_inline_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Process Manager Bot with RAM Cleaner started...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

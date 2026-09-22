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
    await asyncio.sleep(3)
    
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode('utf-8') if proc.stderr else "Unknown error"
        error_msg = stderr[-1000:] if stderr else "No error log captured."
        
        crash_text = (
            f"⚠️ **Script Crash Alert!**\n\n"
            f"📄 File: `{file_name}`\n"
            f"❌ **Error Log:**\n"
            f"```\n{error_msg}\n```"
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=crash_text,
            parse_mode="Markdown"
        )
        if proc.pid in RUNNING_PROCESSES:
            del RUNNING_PROCESSES[proc.pid]

def launch_process(file_path, file_name):
    """File ko execute karke process object return karta hai"""
    proc = None
    if file_name.endswith(".py"):
        proc = subprocess.Popen(
            ["python3", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    elif file_name.endswith(".sh"):
        os.chmod(file_path, 0o755)
        proc = subprocess.Popen(
            ["bash", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    return proc

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
        proc = launch_process(file_path, file_name)
        if not proc:
            await msg.reply_text("📁 File save ho gayi hai lekin auto-run unsupported extension par nahi hoga.", reply_markup=KEYBOARD)
            return

        RUNNING_PROCESSES[proc.pid] = {"file": file_name, "path": file_path, "proc": proc}
        
        control_btns = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🛑 Stop", callback_data=f"stop_{proc.pid}"),
                InlineKeyboardButton(f"🔄 Restart", callback_data=f"restart_{proc.pid}")
            ]
        ])

        await msg.reply_text(
            f"✅ **Script Running!**\n\n"
            f"📄 File: `{file_name}`\n"
            f"🆔 **PID:** `{proc.pid}`",
            parse_mode="Markdown",
            reply_markup=control_btns
        )

        asyncio.create_task(monitor_script_output(proc, file_name, msg.chat_id, context))

    except Exception as e:
        await msg.reply_text(f"❌ Error while running file: `{str(e)}`", parse_mode="Markdown", reply_markup=KEYBOARD)
    
    clear_memory()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#         PROCESS CONTROL FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def list_processes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory()
    if not RUNNING_PROCESSES:
        await update.message.reply_text("📭 Abhi koi bhi script run nahi ho rahi hai.", reply_markup=KEYBOARD)
        return

    text = "⚙️ **Active Running Scripts:**\nNiche kisi bhi script ko **Stop** ya **Restart** karein:\n"
    
    inline_buttons = []
    for pid, data in RUNNING_PROCESSES.items():
        fname = data["file"]
        inline_buttons.append([
            InlineKeyboardButton(f"🛑 Stop {fname}", callback_data=f"stop_{pid}"),
            InlineKeyboardButton(f"🔄 Restart", callback_data=f"restart_{pid}")
        ])

    reply_inline_markup = InlineKeyboardMarkup(inline_buttons)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_inline_markup)

async def handle_inline_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id

    if data.startswith("stop_"):
        pid = int(data.split("_")[1])
        try:
            if pid in RUNNING_PROCESSES or psutil.pid_exists(pid):
                p = psutil.Process(pid)
                p.terminate()
                data_info = RUNNING_PROCESSES.pop(pid, None)
                file_name = data_info["file"] if data_info else "Unknown File"
                await query.edit_message_text(f"🛑 Script `{file_name}` (PID: `{pid}`) ko stop kar diya gaya hai!", parse_mode="Markdown")
            else:
                await query.edit_message_text("❌ Yeh process pehle hi stop ho chuka hai.")
        except Exception as e:
            await query.edit_message_text(f"❌ Process stop karne mein error aaya: `{str(e)}`", parse_mode="Markdown")

    elif data.startswith("restart_"):
        pid = int(data.split("_")[1])
        if pid not in RUNNING_PROCESSES and not psutil.pid_exists(pid):
            await query.edit_message_text("❌ Yeh process pehle hi band ho chuka hai, restart nahi kiya ja sakta.")
            return

        data_info = RUNNING_PROCESSES.pop(pid, None)
        file_name = data_info["file"] if data_info else "Unknown File"
        file_path = data_info["path"] if data_info else os.path.join(HOST_DIR, file_name)

        try:
            if psutil.pid_exists(pid):
                psutil.Process(pid).terminate()
        except Exception:
            pass

        await query.edit_message_text(f"🔄 Restarting `{file_name}`...", parse_mode="Markdown")

        try:
            new_proc = launch_process(file_path, file_name)
            if new_proc:
                RUNNING_PROCESSES[new_proc.pid] = {"file": file_name, "path": file_path, "proc": new_proc}
                
                control_btns = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(f"🛑 Stop", callback_data=f"stop_{new_proc.pid}"),
                        InlineKeyboardButton(f"🔄 Restart", callback_data=f"restart_{new_proc.pid}")
                    ]
                ])

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ **Script Restarted Successfully!**\n\n📄 File: `{file_name}`\n🆔 **New PID:** `{new_proc.pid}`",
                    parse_mode="Markdown",
                    reply_markup=control_btns
                )
                asyncio.create_task(monitor_script_output(new_proc, file_name, chat_id, context))
        except Exception as e:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Error while restarting `{file_name}`: `{str(e)}`",
                parse_mode="Markdown"
            )

    clear_memory()

async def stop_all_processes(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    await update.message.reply_text(
        f"📊 **System Status:**\n\n"
        f"🧠 Main Bot RAM: `{ram_mb:.2f} MB`\n"
        f"⚡ Active Scripts: `{len(RUNNING_PROCESSES)}`",
        parse_mode="Markdown",
        reply_markup=KEYBOARD
    )

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

def main():
    Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_processes))
    app.add_handler(CommandHandler("stopall", stop_all_processes))
    app.add_handler(CommandHandler("ram", ram_status))
    
    app.add_handler(CallbackQueryHandler(handle_inline_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Process Manager with Restart Option started...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

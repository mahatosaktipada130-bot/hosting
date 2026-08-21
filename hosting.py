# ====================================================
#               MADE BY XPILIOT
#     UNLIMITED HOSTING SERVER (RENDER READY)
# ====================================================

from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import sys
import sqlite3
import subprocess
import time
import threading
from datetime import datetime
from telebot import TeleBot, types

# ==================== RENDER DUMMY PORT BINDING ====================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hosting Bot is Running Safely on Render!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# ==================== BOT CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8782806153:AAGz3-X2NLhSjVVyXB-llODBBpV-vcKNHE8")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "echosting_bot")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8084694525))

HOST_DIR = "hosted_files"
MAX_LOG_SIZE_MB = 5

os.makedirs(HOST_DIR, exist_ok=True)

bot = TeleBot(BOT_TOKEN, threaded=True, num_threads=50)

# ==================== DATABASE SETUP ====================
def get_db():
    conn = sqlite3.connect("hosting_data.db", check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    # USERS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)
    # BOTS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosted_bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            filepath TEXT,
            logpath TEXT,
            pid INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'stopped',
            auto_guard INTEGER DEFAULT 1,
            speed_boost INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==================== HELPER FUNCTIONS ====================
def register_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
    conn.close()

def send_or_edit(chat_id, text, reply_markup=None, message_id=None, parse_mode="Markdown"):
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode=parse_mode, reply_markup=reply_markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)

# ==================== CRASH GUARD WORKER ====================
def is_process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def crash_guard_worker():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hosted_bots WHERE status = 'running'")
            running_bots = cursor.fetchall()
            
            for b in running_bots:
                pid = b['pid']
                bot_id = b['id']
                filepath = b['filepath']
                logpath = b['logpath']
                
                if os.path.exists(logpath) and os.path.getsize(logpath) > MAX_LOG_SIZE_MB * 1024 * 1024:
                    try:
                        with open(logpath, 'w', encoding='utf-8') as f:
                            f.write(f"--- [LOG RESET AT {datetime.now()}] ---\n")
                    except Exception:
                        pass

                is_alive = False
                if pid:
                    is_alive = is_process_alive(pid)
                
                if not is_alive:
                    if b['auto_guard'] == 1:
                        try:
                            log_file = open(logpath, 'a', encoding='utf-8')
                            log_file.write(f"\n--- [AUTO RESTART AT {datetime.now()}] ---\n")
                            log_file.flush()
                            
                            proc = subprocess.Popen(
                                [sys.executable, "-u", filepath],
                                stdout=log_file,
                                stderr=log_file,
                                cwd=os.path.dirname(filepath)
                            )
                            log_file.close()
                            cursor.execute("UPDATE hosted_bots SET pid = ? WHERE id = ?", (proc.pid, bot_id))
                            conn.commit()
                        except Exception:
                            cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (bot_id,))
                            conn.commit()
                    else:
                        cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (bot_id,))
                        conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(10)

guard_thread = threading.Thread(target=crash_guard_worker, daemon=True)
guard_thread.start()

# ==================== KEYBOARDS ====================
def main_menu_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 Upload Bot (.py)", callback_data="upload_info"),
        types.InlineKeyboardButton("📱 My Hosted Bots", callback_data="my_bots")
    )
    markup.add(
        types.InlineKeyboardButton("📊 Server Status", callback_data="server_stats"),
        types.InlineKeyboardButton("❓ Help & Guide", callback_data="help_guide")
    )
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
    return markup

# ==================== COMMAND HANDLERS ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    register_user(user_id)
    user_name = message.from_user.first_name or "User"

    welcome_msg = (
        f"🎬 **Made by Xpiliot** 🎬\n"
        f"⚡ **UNLIMITED HOSTING SERVER** ⚡\n\n"
        f"✨ **Welcome, {user_name}!**\n\n"
        f"👤 **User Profile Card:**\n"
        f" ├ 🏷️ **Name:** `{user_name}`\n"
        f" └ 🆔 **User ID:** `{user_id}`\n\n"
        f"⚡ **Services:**\n"
        f" ├ 🚀 **Hosting Limit:** Unlimited\n"
        f" └ 🛡️ **Crash Guard:** 24/7 Enabled\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 **Select an option below:**"
    )
    bot.send_message(message.chat.id, welcome_msg, parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    register_user(user_id)
    
    if not message.document.file_name or not message.document.file_name.endswith('.py'):
        bot.reply_to(message, "❌ **Invalid File Format!** Please upload a `.py` Python script only.")
        return

    filename = message.document.file_name

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM hosted_bots WHERE user_id = ? AND filename = ?", (user_id, filename))
    existing_bot = cursor.fetchone()

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    user_dir = os.path.join(os.getcwd(), HOST_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)

    filepath = os.path.join(user_dir, filename)
    logpath = filepath + ".log"

    with open(filepath, 'wb') as new_file:
        new_file.write(downloaded_file)

    if existing_bot:
        cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (existing_bot['id'],))
    else:
        cursor.execute("INSERT INTO hosted_bots (user_id, filename, filepath, logpath, status) VALUES (?, ?, ?, ?, 'stopped')", 
                       (user_id, filename, filepath, logpath))
    conn.commit()
    conn.close()

    bot.reply_to(message, f"✅ **{filename}** saved successfully!\n\n📱 Click 'My Hosted Bots' to control it.")

# ==================== CALLBACK HANDLER ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if call.data == "main_menu":
        send_or_edit(chat_id, "🏠 **Main Navigation Menu:**", main_menu_keyboard(user_id), msg_id)

    elif call.data == "upload_info":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, "📥 **Please send your `.py` Python file directly into this chat.**", markup, msg_id)

    elif call.data == "server_stats":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM hosted_bots")
        total_bots = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as running FROM hosted_bots WHERE status='running'")
        running_bots = cursor.fetchone()['running']
        conn.close()

        msg = (
            f"🖥️ **Server Real-time Status**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 **Total Bots:** `{total_bots}`\n"
            f"🟢 **Running Bots:** `{running_bots}`"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh Status", callback_data="server_stats"))
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, msg, markup, msg_id)

    elif call.data == "help_guide":
        help_msg = (
            f"❓ **Help & Guide**\n\n"
            f"1️⃣ Upload `.py` file.\n"
            f"2️⃣ Go to **My Hosted Bots**.\n"
            f"3️⃣ Press ▶️ **Start Bot**.\n"
            f"4️⃣ Check **Live Logs** if errors occur."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, help_msg, markup, msg_id)

    elif call.data == "admin_panel":
        if user_id != ADMIN_ID: return
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()['total_users']
        conn.close()

        msg = (
            f"⚙️ **ADMIN CONTROL PANEL** ⚙️\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👥 **Total Registered Users:** `{total_users}`"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, msg, markup, msg_id)

    elif call.data == "my_bots":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hosted_bots WHERE user_id = ?", (user_id,))
        bots = cursor.fetchall()
        conn.close()

        if not bots:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
            send_or_edit(chat_id, "❌ **No uploaded bots found.**", markup, msg_id)
            return

        markup = types.InlineKeyboardMarkup()
        for b in bots:
            icon = "🟢" if (b['status'] == 'running' and b['pid'] and is_process_alive(b['pid'])) else "🔴"
            markup.add(types.InlineKeyboardButton(f"{icon} {b['filename']}", callback_data=f"manage_{b['id']}"))
        
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, "⚙️ **Select a bot to manage:**", markup, msg_id)

    elif call.data.startswith("manage_"):
        bot_id = int(call.data.split("_")[1])
        render_bot_control(chat_id, bot_id, msg_id)

    elif call.data.startswith("startbot_"):
        bot_id = int(call.data.split("_")[1])
        start_bot_action(chat_id, bot_id, msg_id)

    elif call.data.startswith("stopbot_"):
        bot_id = int(call.data.split("_")[1])
        stop_bot_action(chat_id, bot_id, msg_id)

    elif call.data.startswith("logbot_"):
        bot_id = int(call.data.split("_")[1])
        show_logs_action(chat_id, bot_id, msg_id)

    elif call.data.startswith("clearlog_"):
        bot_id = int(call.data.split("_")[1])
        clear_logs_action(chat_id, bot_id, msg_id)

    elif call.data.startswith("piplist_"):
        bot_id = int(call.data.split("_")[1])
        show_pip_action(chat_id, bot_id, msg_id)

    elif call.data.startswith("delbot_"):
        bot_id = int(call.data.split("_")[1])
        delete_bot_action(chat_id, bot_id, msg_id)

# ==================== BOT CONTROL ACTIONS ====================
def render_bot_control(chat_id, bot_id, msg_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()
    conn.close()

    if not b:
        bot.send_message(chat_id, "❌ Bot process not found.")
        return

    is_running = False
    if b['status'] == 'running' and b['pid'] and is_process_alive(b['pid']):
        is_running = True

    status_icon = "🟢 Running" if is_running else "🔴 Stopped"

    msg = (
        f"🤖 **Bot Control Panel**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📄 **File:** `{b['filename']}`\n"
        f"📊 **Status:** {status_icon}\n"
        f"🆔 **PID:** `{b['pid'] if is_running else 'N/A'}`\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.add(types.InlineKeyboardButton("🛑 Stop Bot", callback_data=f"stopbot_{b['id']}"))
    else:
        markup.add(types.InlineKeyboardButton("▶️ Start Bot", callback_data=f"startbot_{b['id']}"))

    markup.add(
        types.InlineKeyboardButton("📜 Live Logs", callback_data=f"logbot_{b['id']}"),
        types.InlineKeyboardButton("🧹 Clear Logs", callback_data=f"clearlog_{b['id']}")
    )
    markup.add(
        types.InlineKeyboardButton("📋 Pip Packages", callback_data=f"piplist_{b['id']}"),
        types.InlineKeyboardButton("🔄 Refresh Panel", callback_data=f"manage_{b['id']}")
    )
    markup.add(types.InlineKeyboardButton("🗑️ Delete Bot", callback_data=f"delbot_{b['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 My Hosted Bots", callback_data="my_bots"))

    send_or_edit(chat_id, msg, markup, msg_id)

def start_bot_action(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()

    if b and (not b['pid'] or not is_process_alive(b['pid'])):
        try:
            log_file = open(b['logpath'], 'a', encoding='utf-8')
            process = subprocess.Popen(
                [sys.executable, "-u", b['filepath']],
                stdout=log_file,
                stderr=log_file,
                cwd=os.path.dirname(b['filepath'])
            )
            log_file.close()
            cursor.execute("UPDATE hosted_bots SET status = 'running', pid = ? WHERE id = ?", (process.pid, bot_id))
            conn.commit()
        except Exception:
            pass
    conn.close()
    render_bot_control(chat_id, bot_id, msg_id)

def stop_bot_action(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()

    if b and b['pid']:
        try:
            if is_process_alive(b['pid']):
                os.kill(b['pid'], 9)
        except Exception:
            pass

    cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()
    render_bot_control(chat_id, bot_id, msg_id)

def show_logs_action(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()
    conn.close()

    if not b or not os.path.exists(b['logpath']):
        bot.send_message(chat_id, "❌ Log file missing.")
        return

    try:
        with open(b['logpath'], 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            last_lines = "".join(lines[-35:])
            
        if not last_lines.strip():
            last_lines = "No logs recorded yet."

        msg = f"📜 **Live Logs for `{b['filename']}`:**\n```\n{last_lines[:3500]}\n```"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Refresh Logs", callback_data=f"logbot_{bot_id}"),
            types.InlineKeyboardButton("🧹 Clear Logs", callback_data=f"clearlog_{bot_id}")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back to Management", callback_data=f"manage_{bot_id}"))
        send_or_edit(chat_id, msg, markup, msg_id)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: `{str(e)}`")

def clear_logs_action(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT logpath FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()
    conn.close()

    if b and os.path.exists(b['logpath']):
        try:
            with open(b['logpath'], 'w', encoding='utf-8') as f:
                f.write("")
        except Exception:
            pass
    show_logs_action(chat_id, bot_id, msg_id)

def show_pip_action(chat_id, bot_id, msg_id):
    try:
        res = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
        packages = res.stdout[:3000]
        msg = f"📋 **Installed Python Packages:**\n```\n{packages}\n```"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Management", callback_data=f"manage_{bot_id}"))
        send_or_edit(chat_id, msg, markup, msg_id)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error getting packages: {str(e)}")

def delete_bot_action(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()

    if b:
        if b['pid'] and is_process_alive(b['pid']):
            try:
                os.kill(b['pid'], 9)
            except Exception:
                pass
        
        if os.path.exists(b['filepath']):
            try: os.remove(b['filepath'])
            except Exception: pass
            
        if os.path.exists(b['logpath']):
            try: os.remove(b['logpath'])
            except Exception: pass

        cursor.execute("DELETE FROM hosted_bots WHERE id = ?", (bot_id,))
        conn.commit()

    conn.close()
    bot.send_message(chat_id, "🗑️ **Bot deleted successfully!**")
    
    # Refresh 'My Hosted Bots' list
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE user_id = ?", (chat_id,))
    bots = cursor.fetchall()
    conn.close()

    if not bots:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, "❌ **No uploaded bots found.**", markup, msg_id)
    else:
        markup = types.InlineKeyboardMarkup()
        for bot_item in bots:
            icon = "🟢" if (bot_item['status'] == 'running' and bot_item['pid'] and is_process_alive(bot_item['pid'])) else "🔴"
            markup.add(types.InlineKeyboardButton(f"{icon} {bot_item['filename']}", callback_data=f"manage_{bot_item['id']}"))
        
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, "⚙️ **Select a bot to manage:**", markup, msg_id)

# ==================== BOT RUNNER ====================
if __name__ == "__main__":
    print("Bot is starting on Render...")
    bot.infinity_polling(skip_pending=True)


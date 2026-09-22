# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime
import psutil
import sqlite3
import logging
import threading
import re
import sys
import gc

# --- Fixed Flask Keep Alive ---
from flask import Flask

app = Flask('')

# Flask ke redundant logs silent karne ke liye
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return "I'm Marco File Host"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def keep_alive():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    print("Flask Keep-Alive server started in background.")

keep_alive()
# --- End Flask Keep Alive ---

# --- Configuration ---
TOKEN = '8688749524:AAHFl91pB4pG4uiThovwi_5uN-eAWfKtklw' # Replace with your actual token
OWNER_ID = 8688749524 # Replace with your Owner ID
YOUR_USERNAME = '@ALONEBOYS777'

# Folder setup - using absolute paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

# Create necessary directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# --- Data structures ---
bot_scripts = {} # {script_key: info_dict}
user_files = {}   # {user_id: [(file_name, file_type), ...]}
active_users = set()

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Command Button Layouts ---
COMMAND_BUTTONS_LAYOUT_USER = [
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "💾 Used RAM"],
    ["📊 Statistics", "🧹 Clear Memory"],
    ["📞 Contact Owner"]
]

# --- Database Setup ---
DB_LOCK = threading.Lock()

def init_db():
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)

def load_data():
    logger.info("Loading data from database...")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()

        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append((file_name, file_type))

        c.execute('SELECT user_id FROM active_users')
        active_users.update(user_id for (user_id,) in c.fetchall())

        conn.close()
        logger.info(f"Data loaded: {len(active_users)} users.")
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}", exc_info=True)

init_db()
load_data()

# --- Render 512MB RAM & Disk Limit Cleanup System ---
def run_memory_and_disk_cleanup():
    """Frees up RAM memory and truncates large logs/temps to handle Render 512MB limit."""
    freed_mb = 0
    try:
        # Python garbage collection
        gc.collect()

        # Clean large logs and temp files in user directories
        for root, dirs, files in os.walk(UPLOAD_BOTS_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                if file.endswith('.log') or file.endswith('.tmp'):
                    try:
                        size = os.path.getsize(file_path)
                        # Truncate logs larger than 1MB
                        if size > 1 * 1024 * 1024:
                            with open(file_path, 'w') as f:
                                f.write("[Log cleared to save Render memory]\n")
                            freed_mb += size / (1024 * 1024)
                    except Exception as err:
                        logger.error(f"Error truncating file {file_path}: {err}")

        # Clean temporary system folders created by zip extraction
        for item in os.listdir(tempfile.gettempdir()):
            if item.startswith("user_") or item.startswith("tmp"):
                item_path = os.path.join(tempfile.gettempdir(), item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        os.remove(item_path)
                except Exception:
                    pass

        logger.info(f"🧹 Auto Cleanup Completed. Cleared roughly {freed_mb:.2f} MB.")
    except Exception as e:
        logger.error(f"Memory cleanup error: {e}")
    return freed_mb

def scheduled_cleaner():
    while True:
        time.sleep(1800) # Runs every 30 minutes
        run_memory_and_disk_cleanup()

cleaner_thread = threading.Thread(target=scheduled_cleaner, daemon=True)
cleaner_thread.start()

# --- Helper Functions ---
def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                    try: script_info['log_file'].close()
                    except Exception: pass
                if script_key in bot_scripts:
                    del bot_scripts[script_key]
            return is_running
        except psutil.NoSuchProcess:
            if script_key in bot_scripts:
                del bot_scripts[script_key]
            return False
        except Exception as e:
            logger.error(f"Error checking process status for {script_key}: {e}")
            return False
    return False

def kill_process_tree(process_info):
    script_key = process_info.get('script_key', 'N/A')
    try:
        if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
            try: process_info['log_file'].close()
            except Exception: pass

        process = process_info.get('process')
        if process and hasattr(process, 'pid'):
            pid = process.pid
            if pid:
                try:
                    parent = psutil.Process(pid)
                    for child in parent.children(recursive=True):
                        child.kill()
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
    except Exception as e:
        logger.error(f"Error killing process tree for {script_key}: {e}")

# --- Script Runners ---
def run_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply):
    script_key = f"{script_owner_id}_{file_name}"
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, f"❌ Error: Script '{file_name}' not found!")
            return

        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.Popen(
            [sys.executable, script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
            stdin=subprocess.PIPE, startupinfo=startupinfo, encoding='utf-8', errors='ignore'
        )

        bot_scripts[script_key] = {
            'process': process, 'log_file': log_file, 'file_name': file_name,
            'script_owner_id': script_owner_id, 'start_time': datetime.now(),
            'user_folder': user_folder, 'type': 'py', 'script_key': script_key
        }
        bot.reply_to(message_obj_for_reply, f"✅ Python script '{file_name}' started! (PID: {process.pid})")
    except Exception as e:
        bot.reply_to(message_obj_for_reply, f"❌ Error starting Python script '{file_name}': {str(e)}")

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply):
    script_key = f"{script_owner_id}_{file_name}"
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, f"❌ Error: Script '{file_name}' not found!")
            return

        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')

        process = subprocess.Popen(
            ['node', script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
            stdin=subprocess.PIPE, encoding='utf-8', errors='ignore'
        )

        bot_scripts[script_key] = {
            'process': process, 'log_file': log_file, 'file_name': file_name,
            'script_owner_id': script_owner_id, 'start_time': datetime.now(),
            'user_folder': user_folder, 'type': 'js', 'script_key': script_key
        }
        bot.reply_to(message_obj_for_reply, f"✅ JS script '{file_name}' started! (PID: {process.pid})")
    except Exception as e:
        bot.reply_to(message_obj_for_reply, f"❌ Error starting JS script: {str(e)}")

# --- Database Operations ---
def save_user_file(user_id, file_name, file_type='py'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)',
                      (user_id, file_name, file_type))
            conn.commit()
            if user_id not in user_files: user_files[user_id] = []
            user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
            user_files[user_id].append((file_name, file_type))
        finally: conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]: del user_files[user_id]
        finally: conn.close()

def add_active_user(user_id):
    active_users.add(user_id)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
        finally: conn.close()

# --- Menu Creation ---
def create_main_menu_inline():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton('📤 Upload File', callback_data='upload'),
        types.InlineKeyboardButton('📂 Check Files', callback_data='check_files'),
        types.InlineKeyboardButton('⚡ Bot Speed', callback_data='speed'),
        types.InlineKeyboardButton('💾 Used RAM', callback_data='ram_usage'),
        types.InlineKeyboardButton('📊 Statistics', callback_data='stats'),
        types.InlineKeyboardButton('🧹 Clear Memory', callback_data='clear_mem'),
        types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}')
    ]
    markup.add(buttons[0], buttons[1])
    markup.add(buttons[2], buttons[3])
    markup.add(buttons[4], buttons[5])
    markup.add(buttons[6])
    return markup

def create_reply_keyboard_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for row_buttons_text in COMMAND_BUTTONS_LAYOUT_USER:
        markup.add(*[types.KeyboardButton(text) for text in row_buttons_text])
    return markup

def create_control_buttons(script_owner_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("🔴 Stop", callback_data=f'stop_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("📜 Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("🟢 Start", callback_data=f'start_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("📜 View Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    markup.add(types.InlineKeyboardButton("🔙 Back to Files", callback_data='check_files'))
    return markup

# --- Handlers Logic ---
def _logic_send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    if user_id not in active_users:
        add_active_user(user_id)

    welcome_msg_text = (f"〽️ Welcome, {user_name}!\n\n🆔 User ID: `{user_id}`\n"
                        f"🤖 Host & run Python (`.py`) or JS (`.js`) scripts.\n\n"
                        f"👇 Use options below to manage your bot scripts.")
    
    bot.send_message(message.chat.id, welcome_msg_text, 
                     reply_markup=create_reply_keyboard_main_menu(), 
                     parse_mode='Markdown')

def _logic_upload_file(message):
    bot.reply_to(message, "📤 Send your Python (`.py`), JS (`.js`), or ZIP (`.zip`) file.")

def _logic_check_files(message):
    user_id = message.from_user.id
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        bot.reply_to(message, "📂 Your files:\n\n(No files uploaded yet)")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(user_files_list):
        is_running = is_bot_running(user_id, file_name)
        status_icon = "🟢 Running" if is_running else "🔴 Stopped"
        btn_text = f"{file_name} ({file_type}) - {status_icon}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'file_{user_id}_{file_name}'))
    bot.reply_to(message, "📂 Your files:\nClick to manage.", reply_markup=markup, parse_mode='Markdown')

def _logic_bot_speed(message):
    start_time_ping = time.time()
    wait_msg = bot.reply_to(message, "🏃 Testing speed...")
    response_time = round((time.time() - start_time_ping) * 1000, 2)
    
    # RAM Usage calculation
    mem = psutil.virtual_memory()
    mem_used_mb = round(mem.used / (1024 * 1024), 2)
    
    speed_msg = (f"⚡ **Bot Speed & System Status**:\n\n"
                 f"⏱️ API Latency: {response_time} ms\n"
                 f"💾 RAM Used: {mem_used_mb} MB / 512 MB\n"
                 f"🟢 System Status: Active")
    bot.edit_message_text(speed_msg, message.chat.id, wait_msg.message_id, parse_mode='Markdown')

def _logic_ram_usage(message):
    mem = psutil.virtual_memory()
    used_mb = round(mem.used / (1024 * 1024), 2)
    free_mb = round(mem.available / (1024 * 1024), 2)
    percent = mem.percent
    
    ram_msg = (f"🖥️ **Render RAM Usage Status**:\n\n"
               f"💾 Used RAM: **{used_mb} MB** / 512 MB\n"
               f"🆓 Free RAM: **{free_mb} MB**\n"
               f"📊 Usage Percentage: **{percent}%**\n")
    bot.reply_to(message, ram_msg, parse_mode='Markdown')

def _logic_clear_system(message):
    wait_msg = bot.reply_to(message, "🧹 Executing Render 512MB Memory & Disk Cleanup...")
    freed = run_memory_and_disk_cleanup()
    bot.edit_message_text(f"✅ **Clear System Executed Successfully!**\n\n"
                          f"🗑️ Freed RAM & Temp Disk Space: ~{freed:.2f} MB\n"
                          f"🚀 Render 512MB limit protection is active.", 
                          message.chat.id, wait_msg.message_id, parse_mode='Markdown')

def _logic_statistics(message):
    user_id = message.from_user.id
    total_users = len(active_users)
    total_files_records = sum(len(files) for files in user_files.values())

    running_bots_count = 0
    for script_key_iter, script_info_iter in list(bot_scripts.items()):
        s_owner_id, _ = script_key_iter.split('_', 1)
        if is_bot_running(int(s_owner_id), script_info_iter['file_name']):
            running_bots_count += 1

    stats_msg = (f"📊 **Bot Statistics**:\n\n"
                 f"👥 Total Users: {total_users}\n"
                 f"📂 Total Files Hosted: {total_files_records}\n"
                 f"🟢 Total Active Running Bots: {running_bots_count}\n")
    bot.reply_to(message, stats_msg, parse_mode='Markdown')

def _logic_contact_owner(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}'))
    bot.reply_to(message, "Click to contact Owner:", reply_markup=markup)

# --- Button Mappings ---
BUTTON_TEXT_TO_LOGIC = {
    "📤 Upload File": _logic_upload_file,
    "📂 Check Files": _logic_check_files,
    "⚡ Bot Speed": _logic_bot_speed,
    "💾 Used RAM": _logic_ram_usage,
    "📊 Statistics": _logic_statistics,
    "🧹 Clear Memory": _logic_clear_system,
    "📞 Contact Owner": _logic_contact_owner,
}

@bot.message_handler(func=lambda message: message.text in BUTTON_TEXT_TO_LOGIC)
def handle_button_text(message):
    logic_func = BUTTON_TEXT_TO_LOGIC.get(message.text)
    if logic_func: logic_func(message)

# --- Clear System Commands/Keywords ---
@bot.message_handler(commands=['clear', 'clean'])
def command_clear(message):
    _logic_clear_system(message)

@bot.message_handler(commands=['ram', 'memory'])
def command_ram(message):
    _logic_ram_usage(message)

@bot.message_handler(func=lambda m: m.text and m.text.lower() in ['clear', 'clean', 'clear system', 'clearsystem'])
def keyword_clear_handler(message):
    _logic_clear_system(message)

@bot.message_handler(commands=['start', 'help'])
def command_send_welcome(message): _logic_send_welcome(message)

# --- Document Handling ---
@bot.message_handler(content_types=['document'])
def handle_file_upload_doc(message):
    user_id = message.from_user.id
    doc = message.document
    file_name = doc.file_name
    
    if not file_name: return
    file_ext = os.path.splitext(file_name)[1].lower()
    
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, "⚠️ Unsupported type! Only `.py`, `.js`, `.zip` allowed.")
        return

    try:
        download_wait_msg = bot.reply_to(message, f"⏳ Downloading `{file_name}`...")
        file_info_tg_doc = bot.get_file(doc.file_id)
        downloaded_file_content = bot.download_file(file_info_tg_doc.file_path)
        bot.edit_message_text(f"✅ Downloaded `{file_name}`. Processing...", message.chat.id, download_wait_msg.message_id)
        
        user_folder = get_user_folder(user_id)
        file_path = os.path.join(user_folder, file_name)
        
        with open(file_path, 'wb') as f: 
            f.write(downloaded_file_content)
        
        save_user_file(user_id, file_name, file_ext.replace('.', ''))
        
        if file_ext == '.js':
            threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, message)).start()
        elif file_ext == '.py':
            threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, message)).start()

    except Exception as e:
        logger.error(f"Error file upload: {e}")
        bot.reply_to(message, f"❌ Error processing file: {str(e)}")

# --- Callbacks ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data

    try:
        if data == 'upload': _logic_upload_file(call.message)
        elif data == 'check_files': _logic_check_files(call.message)
        elif data == 'speed': _logic_bot_speed(call.message)
        elif data == 'ram_usage': _logic_ram_usage(call.message)
        elif data == 'stats': _logic_statistics(call.message)
        elif data == 'clear_mem': _logic_clear_system(call.message)
        elif data.startswith('file_'):
            _, script_owner_id_str, file_name = data.split('_', 2)
            script_owner_id = int(script_owner_id_str)
            is_running = is_bot_running(script_owner_id, file_name)
            bot.edit_message_text(f"⚙️ Controls for `{file_name}`", call.message.chat.id, call.message.message_id,
                                  reply_markup=create_control_buttons(script_owner_id, file_name, is_running), parse_mode='Markdown')
        elif data.startswith('start_'):
            _, script_owner_id_str, file_name = data.split('_', 2)
            user_folder = get_user_folder(int(script_owner_id_str))
            file_path = os.path.join(user_folder, file_name)
            if file_name.endswith('.js'):
                run_js_script(file_path, int(script_owner_id_str), user_folder, file_name, call.message)
            else:
                run_script(file_path, int(script_owner_id_str), user_folder, file_name, call.message)
        elif data.startswith('stop_'):
            _, script_owner_id_str, file_name = data.split('_', 2)
            script_key = f"{script_owner_id_str}_{file_name}"
            if script_key in bot_scripts:
                kill_process_tree(bot_scripts[script_key])
                del bot_scripts[script_key]
            bot.reply_to(call.message, f"🔴 Stopped `{file_name}`", parse_mode='Markdown')
        elif data.startswith('delete_'):
            _, script_owner_id_str, file_name = data.split('_', 2)
            script_key = f"{script_owner_id_str}_{file_name}"
            if script_key in bot_scripts:
                kill_process_tree(bot_scripts[script_key])
                del bot_scripts[script_key]
            remove_user_file_db(int(script_owner_id_str), file_name)
            bot.reply_to(call.message, f"🗑️ Deleted `{file_name}`", parse_mode='Markdown')
        elif data.startswith('logs_'):
            _, script_owner_id_str, file_name = data.split('_', 2)
            user_folder = get_user_folder(int(script_owner_id_str))
            log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()[-3000:]
                bot.send_message(call.message.chat.id, f"📜 **Logs for {file_name}**:\n```\n{content or 'Empty Log'}\n```", parse_mode='Markdown')
            else:
                bot.reply_to(call.message, "⚠️ No log file found.")
    except Exception as e:
        logger.error(f"Callback error: {e}")

bot.infinity_polling(skip_pending=True)


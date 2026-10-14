# -*- coding: utf-8 -*-
import subprocess
import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except:
    pass

# --- AUTO INSTALL DEPENDENCIES ---
def auto_install():
    required = ['pyTelegramBotAPI', 'psutil', 'flask', 'requests']
    for pkg in required:
        try:
            __import__(pkg.lower().replace('pytelegrambotapi','telebot').replace('flask','flask'))
        except ImportError:
            print(f"[AUTO-INSTALL] Installing {pkg}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', pkg, '-q'],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

try:
    import telebot
    import psutil
    from flask import Flask
    import requests
except ImportError:
    auto_install()
    import telebot
    import psutil
    from flask import Flask
    import requests
# --- END AUTO INSTALL ---

import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime
import sqlite3
import json
import logging
import threading
import re
import atexit

from threading import Thread

# ============================================================
# 🔤 SMALL CAPS FONT CONVERTER (ᴀᴘᴘʀᴏᴠᴇᴅ style)
# ============================================================
SMALL_CAPS_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
    'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
    'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ',
    'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
}

def sc(text):
    """Convert normal text to ꜱᴍᴀʟʟ ᴄᴀᴘꜱ style."""
    if text is None:
        return text
    result = []
    for ch in str(text):
        low = ch.lower()
        result.append(SMALL_CAPS_MAP.get(low, ch))
    return ''.join(result)

# ============================================================

app = Flask('')

@app.route('/')
def home():
    return "bot is running...."

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive server started.")

# --- CONFIGURATION ---
TOKEN = "8920262835:AAFwJcfEoI7X1XU3D2wM1MNVrJoXlG_9LqU"  # apna token yaha dalo
OWNER_ID = 0  # apna telegram user id yaha dalo
ADMIN_ID = 0  # admin id yaha dalo (owner jaisa hi rakh sakte ho)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

# All unlimited now — TOTALY FREE
FREE_USER_LIMIT = float('inf')
SUBSCRIBED_USER_LIMIT = float('inf')
ADMIN_LIMIT = float('inf')
OWNER_LIMIT = float('inf')

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN) if TOKEN else None

bot_scripts = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# 🔘 BUTTON LABELS (Small Caps + Emojis)
# ============================================================
BTN_UPLOAD    = sc("📤 Upload File")
BTN_CHECK     = sc("📁 Check Files")
BTN_SPEED     = sc("⚡ Bot Speed")
BTN_STATS     = sc("📊 Statistics")
BTN_CMD       = sc("💻 Send Command")
BTN_BROADCAST = sc("📢 Broadcast")
BTN_LOCK      = sc("🔒 Lock Bot")
BTN_UNLOCK    = sc("🔓 Unlock Bot")
BTN_RUN_ALL   = sc("▶️ Running All Code")
BTN_ADMIN     = sc("⚙️ Admin Panel")
BTN_BACK      = sc("🔙 Back")
BTN_BACK_MAIN = sc("🏠 Back to Main")
BTN_START     = sc("▶️ Start")
BTN_STOP      = sc("⏹ Stop")
BTN_RESTART   = sc("🔄 Restart")
BTN_DELETE    = sc("🗑 Delete")
BTN_LOGS      = sc("📜 Logs")
BTN_VIEW_LOGS = sc("📜 View Logs")

COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    [BTN_UPLOAD, BTN_CHECK],
    [BTN_SPEED, BTN_STATS],
    [BTN_CMD],
]
ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    [BTN_UPLOAD, BTN_CHECK],
    [BTN_SPEED, BTN_STATS],
    [BTN_BROADCAST, BTN_LOCK],
    [BTN_RUN_ALL, BTN_ADMIN],
    [BTN_CMD],
]

def init_db():
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB init error: {e}")

def load_data():
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
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(user_id for (user_id,) in c.fetchall())
        conn.close()
    except Exception as e:
        logger.error(f"Load error: {e}")

if TOKEN:
    init_db()
    load_data()

def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_file_limit(user_id):
    return float('inf')

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

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
            if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                try: script_info['log_file'].close()
                except Exception: pass
            if script_key in bot_scripts:
                del bot_scripts[script_key]
            return False
        except Exception:
            return False
    return False

def kill_process_tree(process_info):
    script_key = process_info.get('script_key', 'N/A')
    try:
        if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
            try: process_info['log_file'].close()
            except Exception: pass
        process = process_info.get('process')
        if process and hasattr(process, 'pid') and process.pid:
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try: child.terminate()
                    except Exception:
                        try: child.kill()
                        except Exception: pass
                gone, alive = psutil.wait_procs(children, timeout=1)
                for p in alive:
                    try: p.kill()
                    except Exception: pass
                try:
                    parent.terminate()
                    try: parent.wait(timeout=1)
                    except psutil.TimeoutExpired: parent.kill()
                except psutil.NoSuchProcess: pass
                except Exception:
                    try: parent.kill()
                    except Exception: pass
            except psutil.NoSuchProcess: pass
    except Exception as e:
        logger.error(f"Kill error for {script_key}: {e}")

TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI', 'telegram': 'python-telegram-bot',
    'python_telegram_bot': 'python-telegram-bot', 'aiogram': 'aiogram',
    'pyrogram': 'pyrogram', 'telethon': 'telethon', 'telepot': 'telepot',
    'tgcrypto': 'tgcrypto', 'bs4': 'beautifulsoup4', 'requests': 'requests',
    'pillow': 'Pillow', 'cv2': 'opencv-python', 'yaml': 'PyYAML',
    'dotenv': 'python-dotenv', 'dateutil': 'python-dateutil',
    'pandas': 'pandas', 'numpy': 'numpy', 'flask': 'Flask',
    'django': 'Django', 'sqlalchemy': 'SQLAlchemy', 'psutil': 'psutil',
    'asyncio': None, 'json': None, 'datetime': None, 'os': None, 'sys': None,
    're': None, 'time': None, 'math': None, 'random': None, 'logging': None,
    'threading': None, 'subprocess': None, 'zipfile': None, 'tempfile': None,
    'shutil': None, 'sqlite3': None, 'atexit': None, 'base64': None,
    'hashlib': None, 'hmac': None, 'struct': None, 'mimetypes': None,
    'signal': None, 'codecs': None, 'string': None, 'glob': None, 'io': None,
}

def attempt_install_pip(module_name, message):
    package_name = TELEGRAM_MODULES.get(module_name.lower(), module_name)
    if module_name.lower() == "pil":
        package_name = "pillow"
    if package_name is None:
        return False
    try:
        bot.reply_to(message, sc(f"📦 Installing {package_name}..."), parse_mode='Markdown')
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', package_name],
                              capture_output=True, text=True, check=False,
                              encoding='utf-8', errors='replace')
        if result.returncode == 0:
            bot.reply_to(message, sc(f"✅ {package_name} installed."), parse_mode='Markdown')
            return True
        else:
            err = f"❌ Failed: {package_name}\n{result.stderr[:500]}"
            bot.reply_to(message, err)
            return False
    except Exception as e:
        bot.reply_to(message, f"❌ Install error: {e}")
        return False

def attempt_install_npm(module_name, user_folder, message):
    try:
        bot.reply_to(message, sc(f"📦 Installing Node {module_name}..."), parse_mode='Markdown')
        result = subprocess.run(['npm', 'install', module_name], capture_output=True,
                              text=True, check=False, cwd=user_folder,
                              encoding='utf-8', errors='replace')
        if result.returncode == 0:
            bot.reply_to(message, sc(f"✅ Node {module_name} installed."), parse_mode='Markdown')
            return True
        else:
            bot.reply_to(message, f"❌ Failed: {module_name}")
            return False
    except FileNotFoundError:
        bot.reply_to(message, sc("❌ npm not found."))
        return False
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")
        return False

def run_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    max_attempts = 3
    if attempt > max_attempts:
        bot.reply_to(message_obj_for_reply, sc(f"❌ Failed to run '{file_name}' after {max_attempts} attempts."))
        return
    script_key = f"{script_owner_id}_{file_name}"
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, sc(f"❌ Script '{file_name}' not found!"))
            if script_owner_id in user_files:
                user_files[script_owner_id] = [f for f in user_files.get(script_owner_id, []) if f[0] != file_name]
            return
        if attempt == 1:
            check_proc = None
            try:
                check_proc = subprocess.Popen([sys.executable, script_path], cwd=user_folder,
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             text=True, encoding='utf-8', errors='replace',
                                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                stdout, stderr = check_proc.communicate(timeout=5)
                rc = check_proc.returncode
                if rc != 0 and stderr:
                    match = re.search(r"ModuleNotFoundError: No module named '(.+?)'", stderr)
                    if match:
                        module_name = match.group(1).strip().split('.')[0]
                        if attempt_install_pip(module_name, message_obj_for_reply):
                            bot.reply_to(message_obj_for_reply, sc(f"🔄 Retrying '{file_name}'..."))
                            time.sleep(2)
                            threading.Thread(target=run_script, args=(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt + 1)).start()
                            return
                        else:
                            bot.reply_to(message_obj_for_reply, sc(f"❌ Install failed for '{module_name}'"))
                            return
                    else:
                        bot.reply_to(message_obj_for_reply, f"❌ Error:\n```{stderr[:500]}```", parse_mode='Markdown')
                        return
            except subprocess.TimeoutExpired:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()
            except Exception as e:
                bot.reply_to(message_obj_for_reply, f"❌ Pre-check error: {e}")
                return
            finally:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        try:
            log_file = open(log_file_path, 'w', encoding='utf-8', errors='replace')
        except Exception as e:
            bot.reply_to(message_obj_for_reply, f"❌ Log file error: {e}")
            return
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen([sys.executable, script_path], cwd=user_folder,
                                       stdout=log_file, stderr=log_file, stdin=subprocess.PIPE,
                                       startupinfo=startupinfo, text=True, encoding='utf-8',
                                       errors='replace', env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            bot_scripts[script_key] = {
                'process': process, 'log_file': log_file, 'file_name': file_name,
                'chat_id': message_obj_for_reply.chat.id, 'script_owner_id': script_owner_id,
                'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'py',
                'script_key': script_key
            }
            bot.reply_to(message_obj_for_reply, sc(f"✅ Python '{file_name}' started!\n🆔 PID: {process.pid}"))
        except Exception as e:
            if log_file and not log_file.closed: log_file.close()
            bot.reply_to(message_obj_for_reply, sc(f"❌ Failed to start: {e}"))
            if script_key in bot_scripts: del bot_scripts[script_key]
    except Exception as e:
        bot.reply_to(message_obj_for_reply, f"❌ Error: {e}")
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    max_attempts = 3
    if attempt > max_attempts:
        bot.reply_to(message_obj_for_reply, sc(f"❌ Failed to run '{file_name}' after {max_attempts} attempts."))
        return
    script_key = f"{script_owner_id}_{file_name}"
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, sc(f"❌ Script '{file_name}' not found!"))
            if script_owner_id in user_files:
                user_files[script_owner_id] = [f for f in user_files.get(script_owner_id, []) if f[0] != file_name]
            return
        if attempt == 1:
            check_proc = None
            try:
                check_proc = subprocess.Popen(['node', script_path], cwd=user_folder,
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             text=True, encoding='utf-8', errors='replace')
                stdout, stderr = check_proc.communicate(timeout=5)
                rc = check_proc.returncode
                if rc != 0 and stderr:
                    match = re.search(r"Cannot find module '(.+?)'", stderr)
                    if match:
                        module_name = match.group(1).strip()
                        if not module_name.startswith('.') and not module_name.startswith('/'):
                            if attempt_install_npm(module_name, user_folder, message_obj_for_reply):
                                bot.reply_to(message_obj_for_reply, sc(f"🔄 Retrying '{file_name}'..."))
                                time.sleep(2)
                                threading.Thread(target=run_js_script, args=(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt + 1)).start()
                                return
                            else:
                                bot.reply_to(message_obj_for_reply, sc(f"❌ Install failed for '{module_name}'"))
                                return
                    bot.reply_to(message_obj_for_reply, f"❌ JS Error:\n```{stderr[:500]}```", parse_mode='Markdown')
                    return
            except subprocess.TimeoutExpired:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()
            except FileNotFoundError:
                bot.reply_to(message_obj_for_reply, sc("❌ Node.js not installed."))
                return
            except Exception as e:
                bot.reply_to(message_obj_for_reply, f"❌ Pre-check error: {e}")
                return
            finally:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        try:
            log_file = open(log_file_path, 'w', encoding='utf-8', errors='replace')
        except Exception as e:
            bot.reply_to(message_obj_for_reply, f"❌ Log file error: {e}")
            return
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(['node', script_path], cwd=user_folder,
                                       stdout=log_file, stderr=log_file, stdin=subprocess.PIPE,
                                       startupinfo=startupinfo, text=True, encoding='utf-8',
                                       errors='replace', env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            bot_scripts[script_key] = {
                'process': process, 'log_file': log_file, 'file_name': file_name,
                'chat_id': message_obj_for_reply.chat.id, 'script_owner_id': script_owner_id,
                'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'js',
                'script_key': script_key
            }
            bot.reply_to(message_obj_for_reply, sc(f"✅ JS '{file_name}' started!\n🆔 PID: {process.pid}"))
        except Exception as e:
            if log_file and not log_file.closed: log_file.close()
            bot.reply_to(message_obj_for_reply, sc(f"❌ Failed to start: {e}"))
            if script_key in bot_scripts: del bot_scripts[script_key]
    except Exception as e:
        bot.reply_to(message_obj_for_reply, f"❌ Error: {e}")
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

DB_LOCK = threading.Lock()

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
        except Exception as e:
            logger.error(f"Save error: {e}")
        finally:
            conn.close()

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
        except Exception as e:
            logger.error(f"Remove error: {e}")
        finally:
            conn.close()

def add_active_user(user_id):
    active_users.add(user_id)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Active user error: {e}")
        finally:
            conn.close()

# ============================================================
# 🎨 MENUS (Small Caps + Emojis)
# ============================================================
def create_main_menu_inline(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(BTN_UPLOAD, callback_data='upload', style="success"),
        types.InlineKeyboardButton(BTN_CHECK, callback_data='check_files', style="primary")
    )
    markup.add(
        types.InlineKeyboardButton(BTN_SPEED, callback_data='speed', style="primary"),
        types.InlineKeyboardButton(BTN_STATS, callback_data='stats', style="primary")
    )
    markup.add(types.InlineKeyboardButton(BTN_CMD, callback_data='send_command', style="primary"))
    if user_id in admin_ids:
        markup.add(
            types.InlineKeyboardButton(BTN_BROADCAST, callback_data='broadcast', style="primary"),
            types.InlineKeyboardButton(BTN_LOCK if not bot_locked else BTN_UNLOCK,
                                     callback_data='lock_bot' if not bot_locked else 'unlock_bot',
                                     style="danger" if not bot_locked else "success")
        )
        markup.add(
            types.InlineKeyboardButton(BTN_RUN_ALL, callback_data='run_all_scripts', style="success"),
            types.InlineKeyboardButton(BTN_ADMIN, callback_data='admin_panel', style="primary")
        )
    return markup

def create_reply_keyboard_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    layout = ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC if user_id in admin_ids else COMMAND_BUTTONS_LAYOUT_USER_SPEC

    def pick_style(text):
        t = text.lower()
        if any(k in t for k in ["lock", "broadcast", "stop", "delete"]):
            return "danger"
        if any(k in t for k in ["upload", "start", "run", "check"]):
            return "success"
        return "primary"

    for row_text in layout:
        row = []
        for text in row_text:
            try:
                row.append(types.KeyboardButton(text=text, style=pick_style(text)))
            except TypeError:
                row.append(types.KeyboardButton(text=text))
        markup.add(*row)
    return markup

def create_control_buttons(script_owner_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton(BTN_STOP, callback_data=f'stop_{script_owner_id}_{file_name}', style="danger"),
            types.InlineKeyboardButton(BTN_RESTART, callback_data=f'restart_{script_owner_id}_{file_name}', style="primary")
        )
        markup.row(
            types.InlineKeyboardButton(BTN_DELETE, callback_data=f'delete_{script_owner_id}_{file_name}', style="danger"),
            types.InlineKeyboardButton(BTN_LOGS, callback_data=f'logs_{script_owner_id}_{file_name}', style="primary")
        )
    else:
        markup.row(
            types.InlineKeyboardButton(BTN_START, callback_data=f'start_{script_owner_id}_{file_name}', style="success"),
            types.InlineKeyboardButton(BTN_DELETE, callback_data=f'delete_{script_owner_id}_{file_name}', style="danger")
        )
        markup.row(
            types.InlineKeyboardButton(BTN_VIEW_LOGS, callback_data=f'logs_{script_owner_id}_{file_name}', style="primary")
        )
    markup.add(types.InlineKeyboardButton(sc("📁 Back to Files"), callback_data='check_files', style="primary"))
    return markup

def create_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton(sc("➕ Add Admin"), callback_data='add_admin', style="success"),
        types.InlineKeyboardButton(sc("➖ Remove Admin"), callback_data='remove_admin', style="danger")
    )
    markup.row(types.InlineKeyboardButton(sc("📋 List Admins"), callback_data='list_admins', style="primary"))
    markup.row(types.InlineKeyboardButton(BTN_BACK_MAIN, callback_data='back_to_main', style="primary"))
    return markup

def create_send_command_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton(sc("📨 Send to Process"), callback_data='send_to_process', style="primary"),
        types.InlineKeyboardButton(sc("📜 View All Logs"), callback_data='view_all_logs', style="primary")
    )
    markup.row(types.InlineKeyboardButton(BTN_BACK_MAIN, callback_data='back_to_main', style="primary"))
    return markup

# --- FILE HANDLING ---
def handle_zip_file(downloaded_file_content, file_name_zip, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        zip_path = os.path.join(temp_dir, file_name_zip)
        with open(zip_path, 'wb') as f:
            f.write(downloaded_file_content)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.infolist():
                member_path = os.path.abspath(os.path.join(temp_dir, member.filename))
                if not member_path.startswith(os.path.abspath(temp_dir)):
                    raise zipfile.BadZipFile(f"Unsafe path: {member.filename}")
            zip_ref.extractall(temp_dir)
        target_dir = temp_dir
        root_files = os.listdir(target_dir)
        if not any(f.endswith(('.py', '.js')) for f in root_files):
            for root, dirs, files in os.walk(temp_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
                if any(f.endswith(('.py', '.js')) for f in files):
                    target_dir = root
                    break
        if target_dir != temp_dir:
            for item in os.listdir(target_dir):
                s = os.path.join(target_dir, item)
                d = os.path.join(temp_dir, item)
                if os.path.exists(d):
                    if os.path.isdir(d): shutil.rmtree(d)
                    else: os.remove(d)
                shutil.move(s, d)
            extracted_items = os.listdir(temp_dir)
        else:
            extracted_items = root_files
        py_files = [f for f in extracted_items if f.endswith('.py')]
        js_files = [f for f in extracted_items if f.endswith('.js')]
        req_file = 'requirements.txt' if 'requirements.txt' in extracted_items else None
        pkg_json = 'package.json' if 'package.json' in extracted_items else None
        if req_file:
            req_path = os.path.join(temp_dir, req_file)
            bot.reply_to(message, sc("📦 Installing Python deps..."))
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_path],
                             capture_output=True, text=True, check=True,
                             encoding='utf-8', errors='ignore')
                bot.reply_to(message, sc("✅ Python deps installed."))
            except subprocess.CalledProcessError as e:
                bot.reply_to(message, f"❌ Py deps failed: {(e.stderr or '')[:400]}"); return
        if pkg_json:
            bot.reply_to(message, sc("📦 Installing Node deps..."))
            try:
                subprocess.run(['npm', 'install'], capture_output=True, text=True,
                             check=True, cwd=temp_dir, encoding='utf-8', errors='ignore')
                bot.reply_to(message, sc("✅ Node deps installed."))
            except FileNotFoundError:
                bot.reply_to(message, sc("❌ npm not found.")); return
            except subprocess.CalledProcessError as e:
                bot.reply_to(message, f"❌ Node deps failed: {(e.stderr or '')[:400]}"); return
        main_script_name = None; file_type = None
        for p in ['main.py', 'bot.py', 'app.py']:
            if p in py_files: main_script_name = p; file_type = 'py'; break
        if not main_script_name:
            for p in ['index.js', 'main.js', 'bot.js', 'app.js']:
                if p in js_files: main_script_name = p; file_type = 'js'; break
        if not main_script_name:
            if py_files: main_script_name = py_files[0]; file_type = 'py'
            elif js_files: main_script_name = js_files[0]; file_type = 'js'
        if not main_script_name:
            bot.reply_to(message, sc("❌ No .py or .js found.")); return
        for item_name in os.listdir(temp_dir):
            if item_name == file_name_zip: continue
            src = os.path.join(temp_dir, item_name)
            dst = os.path.join(user_folder, item_name)
            if os.path.isdir(dst): shutil.rmtree(dst)
            elif os.path.exists(dst): os.remove(dst)
            shutil.move(src, dst)
        save_user_file(user_id, main_script_name, file_type)
        main_path = os.path.join(user_folder, main_script_name)
        bot.reply_to(message, sc(f"✅ Extracted. Starting: {main_script_name}"), parse_mode='Markdown')
        if file_type == 'py':
            threading.Thread(target=run_script, args=(main_path, user_id, user_folder, main_script_name, message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(main_path, user_id, user_folder, main_script_name, message)).start()
    except zipfile.BadZipFile as e:
        bot.reply_to(message, sc(f"❌ Bad ZIP: {e}"))
    except Exception as e:
        bot.reply_to(message, sc(f"❌ ZIP error: {e}"))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir)
            except Exception: pass

def handle_js_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'js')
        threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        bot.reply_to(message, f"❌ JS error: {e}")

def handle_py_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'py')
        threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        bot.reply_to(message, f"❌ PY error: {e}")

# --- LOGIC ---
def _logic_send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    if bot_locked and user_id not in admin_ids:
        bot.send_message(chat_id, sc("🔒 Bot locked by admin. Try later."))
        return
    if user_id not in active_users:
        add_active_user(user_id)
        try:
            bot.send_message(OWNER_ID, sc(f"🆕 New user: {user_name} | ID: {user_id}"), parse_mode='Markdown')
        except Exception: pass
    current_files = get_user_file_count(user_id)
    if user_id == OWNER_ID: status = sc("👑 Owner")
    elif user_id in admin_ids: status = sc("🛡 Admin")
    else: status = sc("👤 User")
    text = (
        sc("🎉 Welcome") + f", {user_name}!\n\n"
        + sc("🆔 ID") + f": `{user_id}`\n"
        + sc("📊 Status") + f": {status}\n"
        + sc("📁 Files") + f": {current_files}\n\n"
        + sc("🚀 Host Python/JS scripts. Upload single files or ZIP.") + "\n\n"
        + sc("👇 Use buttons below.")
    )
    try:
        bot.send_message(chat_id, text, reply_markup=create_reply_keyboard_main_menu(user_id), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Welcome error: {e}")

def _logic_upload_file(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, sc("🔒 Bot locked."))
        return
    bot.reply_to(message, sc("📤 Send your .py, .js, or .zip file."))

def _logic_check_files(message):
    user_id = message.from_user.id
    files_list = user_files.get(user_id, [])
    if not files_list:
        bot.reply_to(message, sc("📂 No files uploaded yet."))
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(files_list):
        is_running = is_bot_running(user_id, file_name)
        icon = sc("🟢 Running") if is_running else sc("🔴 Stopped")
        style = "success" if is_running else "danger"
        markup.add(types.InlineKeyboardButton(f"{file_name} ({file_type}) - {icon}",
                                             callback_data=f'file_{user_id}_{file_name}', style=style))
    bot.reply_to(message, sc("📁 Your files:"), reply_markup=markup)

def _logic_bot_speed(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    t = time.time()
    wait = bot.reply_to(message, sc("⚡ Testing..."))
    try:
        bot.send_chat_action(chat_id, 'typing')
        rt = round((time.time() - t) * 1000, 2)
        status = sc("🔓 Unlocked") if not bot_locked else sc("🔒 Locked")
        bot.edit_message_text(sc(f"⚡ Response: {rt} ms\n🤖 Bot: {status}"), chat_id, wait.message_id)
    except Exception:
        bot.edit_message_text(sc("❌ Error."), chat_id, wait.message_id)

def _logic_statistics(message):
    user_id = message.from_user.id
    total_users = len(active_users)
    total_files = sum(len(f) for f in user_files.values())
    running = 0
    user_running = 0
    for key, info in list(bot_scripts.items()):
        try:
            s_owner = int(key.split('_', 1)[0])
            if is_bot_running(s_owner, info['file_name']):
                running += 1
                if s_owner == user_id: user_running += 1
        except Exception: pass
    text = (
        sc("📊 Statistics") + "\n\n"
        + sc("👥 Users") + f": {total_users}\n"
        + sc("📁 Files") + f": {total_files}\n"
        + sc("🟢 Running") + f": {running}\n"
        + sc("👤 Your Scripts") + f": {user_running}"
    )
    bot.reply_to(message, text)

def _logic_broadcast_init(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, sc("🛡 Admin only."))
        return
    msg = bot.reply_to(message, sc("📢 Send broadcast message.\n❌ /cancel to abort."))
    bot.register_next_step_handler(msg, process_broadcast_message)

def _logic_toggle_lock_bot(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, sc("🛡 Admin only."))
        return
    global bot_locked
    bot_locked = not bot_locked
    bot.reply_to(message, sc(f"🔒 Bot {'locked' if bot_locked else 'unlocked'}."))

def _logic_admin_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, sc("🛡 Admin only."))
        return
    bot.reply_to(message, sc("⚙️ Admin Panel:"), reply_markup=create_admin_panel())

def _logic_send_command(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, sc("🔒 Bot locked."))
        return
    bot.reply_to(message, sc("💻 Send Command:"), reply_markup=create_send_command_menu())

def _logic_run_all_scripts(message_or_call):
    if isinstance(message_or_call, telebot.types.Message):
        admin_id = message_or_call.from_user.id
        chat_id = message_or_call.chat.id
        reply = lambda t, **k: bot.reply_to(message_or_call, t, **k)
        msg_obj = message_or_call
    elif isinstance(message_or_call, telebot.types.CallbackQuery):
        admin_id = message_or_call.from_user.id
        chat_id = message_or_call.message.chat.id
        bot.answer_callback_query(message_or_call.id)
        reply = lambda t, **k: bot.send_message(chat_id, t, **k)
        msg_obj = message_or_call.message
    else:
        return
    if admin_id not in admin_ids:
        reply(sc("🛡 Admin only."))
        return
    reply(sc("🚀 Starting all scripts..."))
    started = 0
    for uid, files in dict(user_files).items():
        ufolder = get_user_folder(uid)
        for fn, ft in files:
            if not is_bot_running(uid, fn):
                fp = os.path.join(ufolder, fn)
                if os.path.exists(fp):
                    try:
                        if ft == 'py':
                            threading.Thread(target=run_script, args=(fp, uid, ufolder, fn, msg_obj)).start()
                            started += 1
                        elif ft == 'js':
                            threading.Thread(target=run_js_script, args=(fp, uid, ufolder, fn, msg_obj)).start()
                            started += 1
                        time.sleep(0.5)
                    except Exception: pass
    reply(sc(f"✅ Started {started} scripts."))

# --- HANDLERS ---
@bot.message_handler(commands=['start', 'help'])
def command_send_welcome(message): _logic_send_welcome(message)

@bot.message_handler(commands=['status'])
def command_show_status(message): _logic_statistics(message)

BUTTON_TEXT_TO_LOGIC = {
    BTN_UPLOAD: _logic_upload_file,
    BTN_CHECK: _logic_check_files,
    BTN_SPEED: _logic_bot_speed,
    BTN_CMD: _logic_send_command,
    BTN_STATS: _logic_statistics,
    BTN_BROADCAST: _logic_broadcast_init,
    BTN_LOCK: _logic_toggle_lock_bot,
    BTN_RUN_ALL: _logic_run_all_scripts,
    BTN_ADMIN: _logic_admin_panel,
}

@bot.message_handler(func=lambda m: m.text in BUTTON_TEXT_TO_LOGIC)
def handle_button_text(message):
    func = BUTTON_TEXT_TO_LOGIC.get(message.text)
    if func: func(message)

@bot.message_handler(commands=['ping'])
def ping(message):
    t = time.time()
    msg = bot.reply_to(message, sc("🏓 Pong!"))
    bot.edit_message_text(sc(f"🏓 Pong! {round((time.time()-t)*1000, 2)} ms"), message.chat.id, msg.message_id)

@bot.message_handler(content_types=['document'])
def handle_file_upload_doc(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    doc = message.document
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, sc("🔒 Bot locked."))
        return
    file_name = doc.file_name
    if not file_name: bot.reply_to(message, sc("❌ No file name.")); return
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, sc("❌ Only .py, .js, .zip allowed."))
        return
    max_size = 20 * 1024 * 1024
    if doc.file_size > max_size:
        bot.reply_to(message, sc(f"❌ Too large (max {max_size//1024//1024}MB).")); return
    try:
        try:
            bot.forward_message(OWNER_ID, chat_id, message.message_id)
            bot.send_message(OWNER_ID, sc(f"📁 File '{file_name}' from {user_id}"))
        except Exception: pass
        wait = bot.reply_to(message, sc(f"📥 Downloading {file_name}..."))
        info = bot.get_file(doc.file_id)
        content = bot.download_file(info.file_path)
        bot.edit_message_text(sc("✅ Downloaded. Processing..."), chat_id, wait.message_id)
        user_folder = get_user_folder(user_id)
        if file_ext == '.zip':
            handle_zip_file(content, file_name, message)
        else:
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f: f.write(content)
            if file_ext == '.js': handle_js_file(file_path, user_id, user_folder, file_name, message)
            elif file_ext == '.py': handle_py_file(file_path, user_id, user_folder, file_name, message)
    except telebot.apihelper.ApiTelegramException as e:
        bot.reply_to(message, f"❌ API Error: {str(e)[:200]}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    if bot_locked and user_id not in admin_ids and data not in ['back_to_main', 'speed', 'stats']:
        bot.answer_callback_query(call.id, sc("🔒 Bot locked."), show_alert=True)
        return
    try:
        if data == 'upload': upload_callback(call)
        elif data == 'check_files': check_files_callback(call)
        elif data.startswith('file_'): file_control_callback(call)
        elif data.startswith('start_'): start_bot_callback(call)
        elif data.startswith('stop_'): stop_bot_callback(call)
        elif data.startswith('restart_'): restart_bot_callback(call)
        elif data.startswith('delete_'): delete_bot_callback(call)
        elif data.startswith('logs_'): logs_bot_callback(call)
        elif data == 'speed': speed_callback(call)
        elif data == 'back_to_main': back_to_main_callback(call)
        elif data.startswith('confirm_broadcast_'): handle_confirm_broadcast(call)
        elif data == 'cancel_broadcast': handle_cancel_broadcast(call)
        elif data == 'send_command': send_command_callback(call)
        elif data == 'send_to_process': send_to_process_callback(call)
        elif data.startswith('sendcmd_select_'): sendcmd_select_callback(call)
        elif data == 'view_all_logs': view_all_logs_callback(call)
        elif data.startswith('viewlog_'): viewlog_callback(call)
        elif data == 'stats': stats_callback(call)
        elif data == 'lock_bot': admin_required_callback(call, lock_bot_callback)
        elif data == 'unlock_bot': admin_required_callback(call, unlock_bot_callback)
        elif data == 'run_all_scripts': admin_required_callback(call, run_all_scripts_callback)
        elif data == 'broadcast': admin_required_callback(call, broadcast_init_callback)
        elif data == 'admin_panel': admin_required_callback(call, admin_panel_callback)
        elif data == 'add_admin': owner_required_callback(call, add_admin_init_callback)
        elif data == 'remove_admin': owner_required_callback(call, remove_admin_init_callback)
        elif data == 'list_admins': admin_required_callback(call, list_admins_callback)
        else:
            bot.answer_callback_query(call.id, sc("❓ Unknown."))
    except Exception as e:
        logger.error(f"Callback error '{data}': {e}")
        try: bot.answer_callback_query(call.id, sc("❌ Error."), show_alert=True)
        except Exception: pass

def admin_required_callback(call, fn):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, sc("🛡 Admin only."), show_alert=True); return
    fn(call)

def owner_required_callback(call, fn):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, sc("👑 Owner only."), show_alert=True); return
    fn(call)

def send_command_callback(call):
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(sc("💻 Send Command:"), call.message.chat.id, call.message.message_id,
                             reply_markup=create_send_command_menu())
    except Exception: pass

def send_to_process_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, sc("📨 Enter command:"))
    bot.register_next_step_handler(msg, lambda m: send_to_process_init(m))

def send_to_process_init(message):
    user_id = message.from_user.id
    running = []
    for key, info in bot_scripts.items():
        if (user_id == info['script_owner_id'] or user_id in admin_ids) and is_bot_running(info['script_owner_id'], info['file_name']):
            running.append((key, info))
    if not running:
        bot.reply_to(message, sc("📂 No running scripts."))
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, info in running:
        markup.add(types.InlineKeyboardButton(f"{info['file_name']} (User {info['script_owner_id']})",
                                             callback_data=f'sendcmd_select_{key}', style="primary"))
    markup.add(types.InlineKeyboardButton(BTN_BACK, callback_data='send_command', style="primary"))
    bot.reply_to(message, sc("🎯 Pick script:"), reply_markup=markup)

def sendcmd_select_callback(call):
    try:
        key = call.data.replace('sendcmd_select_', '')
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, sc(f"💻 Command for {key}:"))
        bot.register_next_step_handler(msg, lambda m: process_send_command(m, key))
    except Exception: pass

def process_send_command(message, key):
    if key not in bot_scripts:
        bot.reply_to(message, sc("❌ Not running.")); return
    info = bot_scripts[key]
    try:
        p = info['process']
        if p and p.poll() is None:
            p.stdin.write(message.text + '\n')
            p.stdin.flush()
            bot.reply_to(message, sc(f"✅ Sent: {message.text}"), parse_mode='Markdown')
        else:
            bot.reply_to(message, sc("❌ Not running."))
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

def view_all_logs_callback(call):
    bot.answer_callback_query(call.id)
    view_all_logs(call.message)

def view_all_logs(message):
    user_id = message.from_user.id
    ufolder = get_user_folder(user_id)
    logs = []
    if os.path.exists(ufolder):
        for f in os.listdir(ufolder):
            if f.endswith('.log'):
                p = os.path.join(ufolder, f)
                logs.append((f, os.path.getsize(p), p))
    if not logs:
        bot.reply_to(message, sc("📂 No logs.")); return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for f, s, p in sorted(logs):
        markup.add(types.InlineKeyboardButton(f"{f} ({s/1024:.1f} KB)",
                                             callback_data=f'viewlog_{user_id}_{f}', style="primary"))
    markup.add(types.InlineKeyboardButton(BTN_BACK, callback_data='send_command', style="primary"))
    bot.reply_to(message, sc("📜 Logs:"), reply_markup=markup)

def viewlog_callback(call):
    try:
        _, uid_str, fname = call.data.split('_', 2)
        uid = int(uid_str)
        if not (call.from_user.id == uid or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, sc("🚫 Not yours."), show_alert=True); return
        p = os.path.join(get_user_folder(uid), fname)
        if not os.path.exists(p):
            bot.answer_callback_query(call.id, sc("❌ Not found."), show_alert=True); return
        bot.answer_callback_query(call.id, sc("📤 Sending..."))
        with open(p, 'rb') as f:
            bot.send_document(call.message.chat.id, f, caption=fname)
    except Exception as e:
        logger.error(f"Viewlog error: {e}")

def upload_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, sc("📤 Send your .py, .js, or .zip file."))

def check_files_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    files_list = user_files.get(user_id, [])
    if not files_list:
        bot.answer_callback_query(call.id, sc("📂 No files."), show_alert=True)
        try:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(BTN_BACK_MAIN, callback_data='back_to_main', style="primary"))
            bot.edit_message_text(sc("📂 No files uploaded."), chat_id, call.message.message_id, reply_markup=markup)
        except Exception: pass
        return
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for fname, ftype in sorted(files_list):
        is_r = is_bot_running(user_id, fname)
        icon = sc("🟢 Running") if is_r else sc("🔴 Stopped")
        style = "success" if is_r else "danger"
        markup.add(types.InlineKeyboardButton(f"{fname} ({ftype}) - {icon}",
                                             callback_data=f'file_{user_id}_{fname}', style=style))
    markup.add(types.InlineKeyboardButton(BTN_BACK_MAIN, callback_data='back_to_main', style="primary"))
    try:
        bot.edit_message_text(sc("📁 Your files:"), chat_id, call.message.message_id, reply_markup=markup)
    except Exception: pass

def file_control_callback(call):
    try:
        _, soid_str, fname = call.data.split('_', 2)
        soid = int(soid_str)
        if not (call.from_user.id == soid or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, sc("🚫 Not yours."), show_alert=True); return
        files_list = user_files.get(soid, [])
        if not any(f[0] == fname for f in files_list):
            bot.answer_callback_query(call.id, sc("❌ Not found."), show_alert=True); return
        bot.answer_callback_query(call.id)
        is_r = is_bot_running(soid, fname)
        ft = next((f[1] for f in files_list if f[0] == fname), '?')
        status = sc('🟢 Running') if is_r else sc('🔴 Stopped')
        try:
            bot.edit_message_text(sc(f"🎛 Controls for {fname} ({ft})\n👤 User: {soid}\n📊 Status: {status}"),
                                 call.message.chat.id, call.message.message_id,
                                 reply_markup=create_control_buttons(soid, fname, is_r))
        except Exception: pass
    except Exception as e:
        bot.answer_callback_query(call.id, sc("❌ Error."), show_alert=True)

def start_bot_callback(call):
    try:
        _, soid_str, fname = call.data.split('_', 2)
        soid = int(soid_str)
        if not (call.from_user.id == soid or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, sc("🚫 Denied."), show_alert=True); return
        files_list = user_files.get(soid, [])
        info = next((f for f in files_list if f[0] == fname), None)
        if not info:
            bot.answer_callback_query(call.id, sc("❌ Not found."), show_alert=True); check_files_callback(call); return
        ft = info[1]
        ufolder = get_user_folder(soid)
        fpath = os.path.join(ufolder, fname)
        if not os.path.exists(fpath):
            bot.answer_callback_query(call.id, sc("❌ File missing."), show_alert=True)
            remove_user_file_db(soid, fname); check_files_callback(call); return
        if is_bot_running(soid, fname):
            bot.answer_callback_query(call.id, sc("🟢 Already running."), show_alert=True); return
        bot.answer_callback_query(call.id, sc(f"🚀 Starting {fname}..."))
        if ft == 'py':
            threading.Thread(target=run_script, args=(fpath, soid, ufolder, fname, call.message)).start()
        elif ft == 'js':
            threading.Thread(target=run_js_script, args=(fpath, soid, ufolder, fname, call.message)).start()
        time.sleep(1.5)
        is_r = is_bot_running(soid, fname)
        status = sc('🟢 Running') if is_r else sc('🟡 Starting...')
        try:
            bot.edit_message_text(sc(f"🎛 Controls for {fname} ({ft})\n👤 User: {soid}\n📊 Status: {status}"),
                                 call.message.chat.id, call.message.message_id,
                                 reply_markup=create_control_buttons(soid, fname, is_r))
        except Exception: pass
    except Exception as e:
        bot.answer_callback_query(call.id, sc("❌ Error."), show_alert=True)

def stop_bot_callback(call):
    try:
        _, soid_str, fname = call.data.split('_', 2)
        soid = int(soid_str)
        if not (call.from_user.id == soid or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, sc("🚫 Denied."), show_alert=True); return
        files_list = user_files.get(soid, [])
        info = next((f for f in files_list if f[0] == fname), None)
        if not info:
            bot.answer_callback_query(call.id, sc("❌ Not found."), show_alert=True); return
        ft = info[1]
        key = f"{soid}_{fname}"
        if not is_bot_running(soid, fname):
            bot.answer_callback_query(call.id, sc("🔴 Already stopped."), show_alert=True)
            try:
                bot.edit_message_text(sc(f"🎛 Controls for {fname} ({ft})\n👤 User: {soid}\n📊 Status: 🔴 Stopped"),
                                     call.message.chat.id, call.message.message_id,
                                     reply_markup=create_control_buttons(soid, fname, False))
            except Exception: pass
            return
        bot.answer_callback_query(call.id, sc("⏹ Stopping..."))
        if key in bot_scripts:
            kill_process_tree(bot_scripts[key])
            del bot_scripts[key]
        try:
            bot.edit_message_text(sc(f"🎛 Controls for {fname} ({ft})\n👤 User: {soid}\n📊 Status: 🔴 Stopped"),
                                 call.message.chat.id, call.message.message_id,
                                 reply_markup=create_control_buttons(soid, fname, False))
        except Exception: pass
    except Exception as e:
        bot.answer_callback_query(call.id, sc("❌ Error."), show_alert=True)

def restart_bot_callback(call):
    try:
        _, soid_str, fname = call.data.split('_', 2)
        soid = int(soid_str)
        if not (call.from_user.id == soid or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, sc("🚫 Denied."), show_alert=True); return
        files_list = user_files.get(soid, [])
        info = next((f for f in files_list if f[0] == fname), None)
        if not info:
            bot.answer_callback_query(call.id, sc("❌ Not found."), show_alert=True); return
        ft = info[1]
        ufolder = get_user_folder(soid)
        fpath = os.path.join(ufolder, fname)
        key = f"{soid}_{fname}"
        if not os.path.exists(fpath):
            bot.answer_callback_query(call.id, sc("❌ File missing."), show_alert=True)
            remove_user_file_db(soid, fname)
            if key in bot_scripts: del bot_scripts[key]
            return
        bot.answer_callback_query(call.id, sc("🔄 Restarting..."))
        if is_bot_running(soid, fname):
            if key in bot_scripts:
                kill_process_tree(bot_scripts[key])
                del bot_scripts[key]
            time.sleep(1.5)
        if ft == 'py':
            threading.Thread(target=run_script, args=(fpath, soid, ufolder, fname, call.message)).start()
        elif ft == 'js':
            threading.Thread(target=run_js_script, args=(fpath, soid, ufolder, fname, call.message)).start()
        time.sleep(1.5)
        is_r = is_bot_running(soid, fname)
        status = sc('🟢 Running') if is_r else sc('🟡 Starting...')
        try:
            bot.edit_message_text(sc(f"🎛 Controls for {fname} ({ft})\n👤 User: {soid}\n📊 Status: {status}"),
                                 call.message.chat.id, call.message.message_id,
                                 reply_markup=create_control_buttons(soid, fname, is_r))
        except Exception: pass
    except Exception as e:
        bot.answer_callback_query(call.id, sc("❌ Error."), show_alert=True)

def delete_bot_callback(call):
    try:
        _, soid_str, fname = call.data.split('_', 2)
        soid = int(soid_str)
        if not (call.from_user.id == soid or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, sc("🚫 Denied."), show_alert=True); return
        files_list = user_files.get(soid, [])
        if not any(f[0] == fname for f in files_list):
            bot.answer_callback_query(call.id, sc("❌ Not found."), show_alert=True); return
        bot.answer_callback_query(call.id, sc("🗑 Deleting..."))
        key = f"{soid}_{fname}"
        if is_bot_running(soid, fname):
            if key in bot_scripts:
                kill_process_tree(bot_scripts[key])
                del bot_scripts[key]
            time.sleep(0.5)
        ufolder = get_user_folder(soid)
        fpath = os.path.join(ufolder, fname)
        lpath = os.path.join(ufolder, f"{os.path.splitext(fname)[0]}.log")
        if os.path.exists(fpath):
            try: os.remove(fpath)
            except Exception: pass
        if os.path.exists(lpath):
            try: os.remove(lpath)
            except Exception: pass
        remove_user_file_db(soid, fname)
        try:
            bot.edit_message_text(sc(f"🗑 Deleted {fname} (User {soid})"),
                                 call.message.chat.id, call.message.message_id,
                                 reply_markup=None)
        except Exception: pass
    except Exception as e:
        bot.answer_callback_query(call.id, sc("❌ Error."), show_alert=True)

def logs_bot_callback(call):
    try:
        _, soid_str, fname = call.data.split('_', 2)
        soid = int(soid_str)
        if not (call.from_user.id == soid or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, sc("🚫 Denied."), show_alert=True); return
        ufolder = get_user_folder(soid)
        lpath = os.path.join(ufolder, f"{os.path.splitext(fname)[0]}.log")
        if not os.path.exists(lpath):
            bot.answer_callback_query(call.id, sc("📂 No logs."), show_alert=True); return
        bot.answer_callback_query(call.id)
        try:
            size = os.path.getsize(lpath)
            max_kb = 100
            max_tg = 4096
            if size == 0:
                content = "(empty)"
            elif size > max_kb * 1024:
                with open(lpath, 'rb') as f:
                    f.seek(-max_kb * 1024, os.SEEK_END)
                    content = f.read().decode('utf-8', errors='ignore')
                content = f"(Last {max_kb} KB)\n" + content
            else:
                with open(lpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            if len(content) > max_tg:
                content = "..." + content[-max_tg:]
            bot.send_message(call.message.chat.id, sc(f"📜 Logs {fname}:") + f"\n```\n{content}\n```", parse_mode='Markdown')
        except Exception as e:
            bot.send_message(call.message.chat.id, sc(f"❌ Error reading log: {e}"))
    except Exception as e:
        bot.answer_callback_query(call.id, sc("❌ Error."), show_alert=True)

def speed_callback(call):
    user_id = call.from_user.id
    t = time.time()
    try:
        bot.edit_message_text(sc("⚡ Testing..."), call.message.chat.id, call.message.message_id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        rt = round((time.time() - t) * 1000, 2)
        status = sc("🔓 Unlocked") if not bot_locked else sc("🔒 Locked")
        bot.answer_callback_query(call.id)
        bot.edit_message_text(sc(f"⚡ Response: {rt} ms\n🤖 Bot: {status}"), call.message.chat.id, call.message.message_id,
                             reply_markup=create_main_menu_inline(user_id))
    except Exception:
        bot.answer_callback_query(call.id, sc("❌ Error."), show_alert=True)

def back_to_main_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    count = get_user_file_count(user_id)
    if user_id == OWNER_ID: status = sc("👑 Owner")
    elif user_id in admin_ids: status = sc("🛡 Admin")
    else: status = sc("👤 User")
    text = (
        sc("🎉 Welcome back") + f", {call.from_user.first_name}!\n\n"
        + sc("🆔 ID") + f": `{user_id}`\n"
        + sc("📊 Status") + f": {status}\n"
        + sc("📁 Files") + f": {count}"
    )
    try:
        bot.answer_callback_query(call.id)
        bot.edit_message_text(text, chat_id, call.message.message_id,
                             reply_markup=create_main_menu_inline(user_id), parse_mode='Markdown')
    except Exception: pass

def stats_callback(call):
    bot.answer_callback_query(call.id)
    _logic_statistics(call.message)
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=create_main_menu_inline(call.from_user.id))
    except Exception: pass

def lock_bot_callback(call):
    global bot_locked; bot_locked = True
    bot.answer_callback_query(call.id, sc("🔒 Locked."))
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                        reply_markup=create_main_menu_inline(call.from_user.id))
    except Exception: pass

def unlock_bot_callback(call):
    global bot_locked; bot_locked = False
    bot.answer_callback_query(call.id, sc("🔓 Unlocked."))
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                        reply_markup=create_main_menu_inline(call.from_user.id))
    except Exception: pass

def run_all_scripts_callback(call): _logic_run_all_scripts(call)

def broadcast_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, sc("📢 Send broadcast.\n❌ /cancel to abort."))
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, sc("🚫 Not authorized.")); return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, sc("❌ Cancelled.")); return
    content = message.text
    if not content and not (message.photo or message.video):
        bot.reply_to(message, sc("❌ Empty message."))
        return
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(sc("✅ Confirm"), callback_data=f"confirm_broadcast_{message.message_id}", style="success"),
        types.InlineKeyboardButton(sc("❌ Cancel"), callback_data="cancel_broadcast", style="danger")
    )
    preview = content[:500] if content else "(Media)"
    bot.reply_to(message, sc(f"📢 Confirm broadcast to {len(active_users)} users?") + f"\n\n{preview}",
                reply_markup=markup)

def handle_confirm_broadcast(call):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, sc("🛡 Admin only."), show_alert=True); return
    try:
        orig = call.message.reply_to_message
        if not orig: raise ValueError("No original")
        b_text = orig.text if orig.text else None
        b_photo = orig.photo[-1].file_id if orig.photo else None
        b_video = orig.video.file_id if orig.video else None
        bot.answer_callback_query(call.id, sc("🚀 Starting..."))
        bot.edit_message_text(sc(f"📢 Broadcasting to {len(active_users)} users..."),
                             call.message.chat.id, call.message.message_id, reply_markup=None)
        threading.Thread(target=execute_broadcast, args=(b_text, b_photo, b_video,
                        orig.caption if (b_photo or b_video) else None, call.message.chat.id)).start()
    except Exception as e:
        bot.edit_message_text(sc(f"❌ Error: {e}"), call.message.chat.id, call.message.message_id)

def handle_cancel_broadcast(call):
    bot.answer_callback_query(call.id, sc("❌ Cancelled."))
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception: pass

def execute_broadcast(b_text, photo, video, caption, chat_id):
    sent = 0; failed = 0
    for uid in list(active_users):
        try:
            if b_text: bot.send_message(uid, b_text)
            elif photo: bot.send_photo(uid, photo, caption=caption)
            elif video: bot.send_video(uid, video, caption=caption)
            sent += 1
        except Exception:
            failed += 1
        time.sleep(0.05)
    try:
        bot.send_message(chat_id, sc(f"✅ Broadcast done.\n📤 Sent: {sent}\n❌ Failed: {failed}"))
    except Exception: pass

def admin_panel_callback(call):
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(sc("⚙️ Admin Panel:"), call.message.chat.id, call.message.message_id,
                             reply_markup=create_admin_panel())
    except Exception: pass

def add_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, sc("➕ Enter user ID to promote.\n❌ /cancel to abort."))
    bot.register_next_step_handler(msg, process_add_admin_id)

def process_add_admin_id(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, sc("👑 Owner only.")); return
    if message.text.lower() == '/cancel':
        bot.reply_to(message, sc("❌ Cancelled.")); return
    try:
        uid = int(message.text.strip())
        if uid <= 0: raise ValueError("bad")
        if uid == OWNER_ID:
            bot.reply_to(message, sc("👑 Already owner.")); return
        if uid in admin_ids:
            bot.reply_to(message, sc("🛡 Already admin.")); return
        admin_ids.add(uid)
        with DB_LOCK:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (uid,))
            conn.commit(); conn.close()
        bot.reply_to(message, sc(f"✅ {uid} is now admin."), parse_mode='Markdown')
        try: bot.send_message(uid, sc("🛡 You are now Admin."))
        except Exception: pass
    except ValueError:
        bot.reply_to(message, sc("❌ Invalid ID."))
        msg = bot.send_message(message.chat.id, sc("➕ Enter ID or /cancel."))
        bot.register_next_step_handler(msg, process_add_admin_id)

def remove_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, sc("➖ Enter admin ID to remove.\n❌ /cancel to abort."))
    bot.register_next_step_handler(msg, process_remove_admin_id)

def process_remove_admin_id(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, sc("👑 Owner only.")); return
    if message.text.lower() == '/cancel':
        bot.reply_to(message, sc("❌ Cancelled.")); return
    try:
        uid = int(message.text.strip())
        if uid <= 0: raise ValueError("bad")
        if uid == OWNER_ID:
            bot.reply_to(message, sc("🚫 Cannot remove owner.")); return
        if uid not in admin_ids:
            bot.reply_to(message, sc("❌ Not admin.")); return
        admin_ids.discard(uid)
        with DB_LOCK:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('DELETE FROM admins WHERE user_id = ?', (uid,))
            conn.commit(); conn.close()
        bot.reply_to(message, sc(f"✅ {uid} removed."), parse_mode='Markdown')
        try: bot.send_message(uid, sc("❌ You are no longer admin."))
        except Exception: pass
    except ValueError:
        bot.reply_to(message, sc("❌ Invalid ID."))
        msg = bot.send_message(message.chat.id, sc("➖ Enter ID or /cancel."))
        bot.register_next_step_handler(msg, process_remove_admin_id)

def list_admins_callback(call):
    bot.answer_callback_query(call.id)
    try:
        lst = "\n".join(f"- `{a}` {'👑 (Owner)' if a == OWNER_ID else '🛡'}" for a in sorted(admin_ids))
        if not lst: lst = "(none)"
        bot.edit_message_text(sc("📋 Admins:") + f"\n\n{lst}", call.message.chat.id, call.message.message_id,
                             reply_markup=create_admin_panel(), parse_mode='Markdown')
    except Exception: pass

def cleanup():
    logger.warning("Shutting down. Cleaning up...")
    for key in list(bot_scripts.keys()):
        if key in bot_scripts:
            kill_process_tree(bot_scripts[key])
atexit.register(cleanup)

if __name__ == '__main__':
    if not TOKEN:
        print("=" * 50)
        print("ERROR: TOKEN empty!")
        print("Open the script and set TOKEN, OWNER_ID, ADMIN_ID")
        print("=" * 50)
        sys.exit(1)
    logger.info("Bot starting...")
    keep_alive()
    while True:
        try:
            bot.infinity_polling(logger_level=logging.INFO, timeout=60, long_polling_timeout=30)
        except requests.exceptions.ReadTimeout:
            time.sleep(5)
        except requests.exceptions.ConnectionError:
            time.sleep(15)
        except Exception as e:
            logger.critical(f"Polling error: {e}", exc_info=True)
            time.sleep(30)

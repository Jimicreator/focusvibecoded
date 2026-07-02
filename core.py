# core.py
import os
import time
import json
import winreg
import ctypes
import threading
import subprocess
import socket
import zlib
import base64
from datetime import datetime

INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
STATE_FILE = os.path.expanduser(r"~\Documents\focus_state_encrypted.dat")
PROXY_PORT = 8080

# Global State Memory - Now includes history
focus_state = {
    "is_active": False,
    "end_time": 0,
    "start_time": 0,
    "blocklist": [],
    "whitelist": [],
    "violations": {"apps": {}, "sites": {}},
    "history": [] 
}

def refresh_network():
    ctypes.windll.wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
    ctypes.windll.wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)

def save_state():
    try:
        raw_data = json.dumps(focus_state).encode('utf-8')
        compressed = zlib.compress(raw_data)
        encrypted = base64.b64encode(compressed)
        with open(STATE_FILE, 'wb') as f:
            f.write(encrypted)
    except Exception as e:
        print("Storage error:", e)

def load_state():
    global focus_state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'rb') as f:
                encrypted = f.read()
            compressed = base64.b64decode(encrypted)
            raw_data = zlib.decompress(compressed).decode('utf-8')
            loaded_data = json.loads(raw_data)
            focus_state.update(loaded_data)
            # Ensure history exists for older save files
            if "history" not in focus_state:
                focus_state["history"] = []
        except Exception:
            pass

def log_violation(category, item):
    if item not in focus_state["violations"][category]:
        focus_state["violations"][category][item] = 0
    focus_state["violations"][category][item] += 1
    save_state()

def apply_network_rules():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{PROXY_PORT}")
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, ";".join(focus_state["whitelist"]))
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        refresh_network()
    except Exception:
        pass

def remove_network_rules():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        refresh_network()
    except Exception:
        pass

def enforcement_loop():
    while focus_state["is_active"] and time.time() < focus_state["end_time"]:
        try:
            output = subprocess.check_output('tasklist /FO CSV /NH', shell=True).decode('utf-8', 'ignore')
            running_exes = [line.split('","')[0].strip('"').lower() for line in output.splitlines() if line]
            
            for exe in focus_state["blocklist"]:
                if exe.lower() in running_exes:
                    log_violation("apps", exe)
                    subprocess.run(f"taskkill /IM {exe} /F", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass
        time.sleep(2)
    
    if focus_state["is_active"]:
        stop_lockdown()

def blackhole_proxy():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', PROXY_PORT))
    server.listen(100)
    server.settimeout(1.0)
    
    while focus_state["is_active"]:
        try:
            client, addr = server.accept()
            data = client.recv(1024).decode('utf-8', 'ignore')
            if data.startswith("CONNECT"):
                domain = data.split(' ')[1].split(':')[0]
                log_violation("sites", domain)
            client.close()
        except socket.timeout:
            continue
        except Exception:
            pass
    server.close()

def start_lockdown(duration_seconds, apps, sites):
    focus_state["start_time"] = time.time()
    focus_state["end_time"] = time.time() + duration_seconds
    focus_state["blocklist"] = apps
    focus_state["whitelist"] = sites
    focus_state["violations"] = {"apps": {}, "sites": {}}
    focus_state["is_active"] = True
    
    save_state()
    apply_network_rules()
    
    threading.Thread(target=blackhole_proxy, daemon=True).start()
    threading.Thread(target=enforcement_loop, daemon=True).start()

def stop_lockdown():
    # Only record history if a session actually finished naturally
    if focus_state["is_active"]:
        actual_duration = time.time() - focus_state["start_time"]
        app_blocks = sum(focus_state["violations"]["apps"].values())
        site_blocks = sum(focus_state["violations"]["sites"].values())
        
        focus_state["history"].append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "duration": actual_duration,
            "app_blocks": app_blocks,
            "site_blocks": site_blocks
        })
        
    focus_state["is_active"] = False
    save_state() # We no longer delete the file. We save the history.
    remove_network_rules()

def resume_from_boot():
    load_state()
    if focus_state["is_active"] and time.time() < focus_state["end_time"]:
        apply_network_rules()
        threading.Thread(target=blackhole_proxy, daemon=True).start()
        threading.Thread(target=enforcement_loop, daemon=True).start()
    elif focus_state["is_active"]:
        # Time expired while PC was off
        stop_lockdown()
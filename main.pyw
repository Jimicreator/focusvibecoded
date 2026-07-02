# main.pyw
import threading
import subprocess
import time
import core
from app import app

def launch_server():
    # Flask runs continuously in the background on port 5000
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    # 1. On boot, check if a session was interrupted
    core.resume_from_boot()
    
    # 2. Start the web server in a background thread
    threading.Thread(target=launch_server, daemon=True).start()
    
    # 3. Give the server a second to boot, then open the UI
    time.sleep(1.5)
    
    # If a session is active from boot, open the Portal directly
    if core.focus_state["is_active"]:
        subprocess.run("start http://localhost:5000/portal", shell=True)
    else:
        subprocess.run("start http://localhost:5000", shell=True)
    
    # 4. Keep the invisible Python process alive
    while True:
        time.sleep(60)
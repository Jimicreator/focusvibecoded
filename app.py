# app.py
from flask import Flask, request, jsonify, render_template
import core
import subprocess
import time

app = Flask(__name__)

# Load history immediately on boot
core.load_state()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/portal')
def portal():
    return render_template('portal.html')

@app.route('/api/apps', methods=['GET'])
def get_running_apps():
    try:
        output = subprocess.check_output('tasklist /FO CSV /NH', shell=True).decode('utf-8', 'ignore')
        running = set()
        for line in output.splitlines():
            if line:
                parts = line.split('","')
                if len(parts) > 0:
                    exe = parts[0].strip('"')
                    if exe.lower().endswith('.exe'):
                        running.add(exe)
        
        ignore = ['svchost.exe', 'explorer.exe', 'cmd.exe', 'conhost.exe', 'tasklist.exe', 'System Idle Process']
        clean = sorted([a for a in running if a.lower() not in ignore])
        return jsonify({"apps": clean})
    except:
        return jsonify({"apps": []})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    # Pass the full state down to the portal for rendering
    return jsonify({
        "is_active": core.focus_state["is_active"],
        "end_time": core.focus_state["end_time"],
        "current_time": time.time(),
        "whitelist": core.focus_state["whitelist"],
        "violations": core.focus_state["violations"],
        "history": core.focus_state["history"]
    })

@app.route('/api/start', methods=['POST'])
def start_api():
    data = request.json
    total_seconds = (data.get('days', 0) * 86400) + (data.get('hours', 0) * 3600) + (data.get('mins', 0) * 60)
    
    if total_seconds <= 0:
        return jsonify({"error": "Invalid time"}), 400

    apps = data.get('apps', [])
    sites = data.get('sites', "").split(';')
    
    core.start_lockdown(total_seconds, apps, sites)
    return jsonify({"status": "locked"})

@app.route('/api/stop', methods=['POST'])
def stop_api():
    core.stop_lockdown()
    return jsonify({"status": "stopped"})
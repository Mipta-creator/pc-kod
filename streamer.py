import cv2, numpy as np, mss, pyautogui, threading, time, psutil, os, ctypes, pyperclip, sys
from flask import Flask, Response, request, render_template_string, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from functools import wraps

# Fix pro DPI
try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
except: pass

pyautogui.FAILSAFE = False
app = Flask(__name__)
CORS(app)

# AUTHENTICATION
UZIVATEL = "admin"
HESLO = "heslo123"

def check_auth(u, p): return u == UZIVATEL and p == HESLO
def authenticate(): return Response('Přihlaš se:', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password): return authenticate()
        return f(*args, **kwargs)
    return decorated

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
    <style>
        body { margin:0; background:#111; color:white; font-family:sans-serif; text-align:center; }
        #stream { width: 100vw; height: 35vh; object-fit: contain; background: #000; touch-action: none; cursor: pointer; }
        #stream:fullscreen { width: 100vw; height: 100vh; object-fit: contain; background: #000; }
        .panel { padding: 8px; background: #222; display: flex; flex-wrap: wrap; justify-content: center; gap: 4px; align-items: center; }
        button { padding: 8px 12px; border-radius: 5px; border: none; background: #444; color: white; cursor: pointer; font-size: 13px; }
        button:active { background: #666; }
        input, select { padding: 8px; border-radius: 5px; border: none; background: #333; color: white; }
        .section-title { font-size: 11px; color: #888; width: 100%; margin-top: 5px; text-transform: uppercase; letter-spacing: 1px; }
        #touchpadArea { display: none; width: 94vw; height: 160px; background: #2a2a2a; border: 2px dashed #555; border-radius: 8px; margin: 8px auto; touch-action: none; align-items: center; justify-content: center; color: #aaa; font-size: 14px; user-select: none; }
    </style>
</head>
<body>
    <!-- Správa PC a Server -->
    <div class="panel">
        <select id="targetIp" onchange="changeTargetPC()"></select>
        <button onclick="openPcManager()" style="background:#056;">⚙️ Správa PC</button>
        <button onclick="startVoice()">🎙️ Hlas</button>
        <button onclick="if(confirm('Opravdu ukončit server?')) cmd('shutdown_server')" style="background:#500;">🔴 Stop</button>
    </div>

    <!-- Modální okno / panel pro správu PC -->
    <div id="pcManagerPanel" class="panel" style="display:none; background:#181818; border-bottom: 2px solid #444;">
        <div class="section-title">Přidat / Upravit zařízení (PC)</div>
        <input type="text" id="newPcName" placeholder="Název (např. Notebook)" style="width:130px;">
        <input type="text" id="newPcUrl" placeholder="URL (např. http://192.168.0.110:5000)" style="flex:1; min-width:180px;">
        <button onclick="saveNewPC()" style="background:#060;">➕ Přidat PC</button>
        <button onclick="removeCurrentPC()" style="background:#600;">🗑️ Smazat vybrané</button>
    </div>

    <!-- Stream / Obrazovka -->
    <div>
        <img id="stream" src="" onclick="handleStreamClick(event)" ondblclick="toggleFullscreen()">
    </div>

    <!-- Šedé pole pro Touchpad -->
    <div id="touchpadArea">
        🖱️ Touchpad plocha (táhni prstem sem pro pohyb myši)
    </div>

    <!-- Ovládání Streamu & Touchpadu -->
    <div class="panel">
        <div class="section-title">Zobrazení a Režim</div>
        <select id="monitorSelect" onchange="updateStreamConfig()">
            <option value="1">Monitor 1</option>
            <option value="2">Monitor 2</option>
        </select>
        <select id="qualitySelect" onchange="updateStreamConfig()">
            <option value="0.2">Nízká kvalita (Rychlá)</option>
            <option value="0.4" selected>Střední kvalita</option>
            <option value="0.7">Vysoká kvalita (HD)</option>
        </select>
        <button onclick="toggleFullscreen()" style="background:#336;">🖥️ Celá obrazovka</button>
        <button id="modeBtn" onclick="toggleTouchpadMode()" style="background:#262;">Mode: Kliknutí</button>
    </div>

    <!-- Touchpad ovládací lišta -->
    <div id="touchpadBar" class="panel" style="display:none; background:#181818;">
        <button onclick="cmd('right_click')">🖱️ Pravý klik</button>
        <button onclick="cmd('scroll_up')">⬆️ Scroll</button>
        <button onclick="cmd('scroll_down')">⬇️ Scroll</button>
        <button id="dragBtn" onclick="toggleDrag()">✋ Držet (Drag)</button>
    </div>

    <!-- Multimédia a Hlasitost -->
    <div class="panel">
        <div class="section-title">Média a Hlasitost</div>
        <button onclick="cmd('vol_mute')">🔇 Mute</button>
        <button onclick="cmd('vol_down')">🔉 -</button>
        <button onclick="cmd('vol_up')">🔊 +</button>
        <button onclick="cmd('media_prev')">⏮️</button>
        <button onclick="cmd('media_play')">⏯️ Play/Pause</button>
        <button onclick="cmd('media_next')">⏭️</button>
    </div>

    <!-- Klávesové zkratky -->
    <div class="panel">
        <div class="section-title">Klávesové zkratky</div>
        <button onclick="cmd('key_enter')">Enter</button>
        <button onclick="cmd('key_backspace')">⌫ Back</button>
        <button onclick="cmd('key_space')">Space</button>
        <button onclick="cmd('key_tab')">Tab</button>
        <button onclick="cmd('key_esc')">Esc</button>
        <button onclick="cmd('key_alttab')">Alt + Tab</button>
        <button onclick="cmd('key_wind')">Win + D</button>
    </div>

    <div class="panel">
        <input type="text" id="customShortcut" placeholder="např. ctrl,c nebo win,r" style="flex:1; min-width:140px;">
        <button onclick="sendCustomShortcut()">Stisknout zkratku</button>
    </div>

    <!-- Spouštěče aplikací -->
    <div class="panel">
        <div class="section-title">Rychlé spouštěče (Quick Launch)</div>
        <button onclick="cmd('launch_chrome')">🌐 Chrome</button>
        <button onclick="cmd('launch_spotify')">🎵 Spotify</button>
        <button onclick="cmd('launch_steam')">🎮 Steam</button>
        <button onclick="cmd('launch_calc')">🧮 Kalkulačka</button>
        <button onclick="cmd('launch_notepad')">📝 Poznámkový blok</button>
        <button onclick="cmd('kill_chrome')" style="background:#600;">❌ Kill Chrome</button>
    </div>

    <!-- Správa napájení -->
    <div class="panel">
        <div class="section-title">Správa napájení</div>
        <button onclick="cmd('lock_pc')">🔒 Zamknout</button>
        <button onclick="cmd('sleep_pc')" style="background:#530;">💤 Uspat</button>
        <button onclick="confirmAndCmd('restart_pc', 'Opravdu restartovat PC?')" style="background:#840;">🔄 Restart</button>
        <button onclick="confirmAndCmd('shutdown_pc', 'Opravdu vypnout PC?')" style="background:#800;">⏻ Vypnout</button>
    </div>

    <!-- Soubory, Schránka a Aktualizace kódu -->
    <div class="panel">
        <div class="section-title">Schránka, Soubory a OTA Kód</div>
        <input type="text" id="clipText" placeholder="Text pro clipboard..." style="flex:1; min-width:140px;">
        <button onclick="sendClip()">📋 Sync</button>
        <button onclick="document.getElementById('fileInput').click()">📤 Soubor</button>
        <input type="file" id="fileInput" style="display:none" onchange="uploadFile()">
        <button onclick="document.getElementById('codeUploadInput').click()" style="background:#056;">📥 Aktualizovat kód</button>
        <input type="file" id="codeUploadInput" style="display:none" accept=".py" onchange="uploadCode()">
    </div>

    <div id="stats" style="font-size:12px; color:#0f0; padding: 5px; background:#000;">CPU: -- | RAM: --</div>

    <script>
        let defaultPCs = [
            { name: "Tento počítač (Lokální)", url: window.location.origin }
        ];

        function getStoredPCs() {
            let data = localStorage.getItem('remote_pcs');
            if (!data) {
                localStorage.setItem('remote_pcs', JSON.stringify(defaultPCs));
                return defaultPCs;
            }
            return JSON.parse(data);
        }

        function initPcDropdown() {
            let pcs = getStoredPCs();
            let select = document.getElementById('targetIp');
            select.innerHTML = '';
            pcs.forEach((pc, idx) => {
                let opt = document.createElement('option');
                opt.value = pc.url;
                opt.innerText = pc.name;
                select.appendChild(opt);
            });
            let activeUrl = localStorage.getItem('active_pc_url');
            if (activeUrl) {
                select.value = activeUrl;
            }
            if (!select.value && pcs.length > 0) {
                select.value = pcs[0].url;
            }
        }

        initPcDropdown();
        let baseUrl = document.getElementById('targetIp').value;

        function changeTargetPC() {
            let select = document.getElementById('targetIp');
            baseUrl = select.value;
            localStorage.setItem('active_pc_url', baseUrl);
            updateStreamFeed();
        }

        function openPcManager() {
            let panel = document.getElementById('pcManagerPanel');
            panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
            document.getElementById('newPcUrl').value = baseUrl;
        }

        function saveNewPC() {
            let name = document.getElementById('newPcName').value.trim();
            let url = document.getElementById('newPcUrl').value.trim();
            if (!name || !url) {
                alert('Vyplň název i URL adresu!');
                return;
            }
            let pcs = getStoredPCs();
            pcs.push({ name: name, url: url });
            localStorage.setItem('remote_pcs', JSON.stringify(pcs));
            document.getElementById('newPcName').value = '';
            initPcDropdown();
            document.getElementById('targetIp').value = url;
            changeTargetPC();
            document.getElementById('pcManagerPanel').style.display = 'none';
        }

        function removeCurrentPC() {
            let select = document.getElementById('targetIp');
            let urlToRemove = select.value;
            let pcs = getStoredPCs();
            if (pcs.length <= 1) {
                alert('Musíš tu mít alespoň jedno zařízení!');
                return;
            }
            pcs = pcs.filter(p => p.url !== urlToRemove);
            localStorage.setItem('remote_pcs', JSON.stringify(pcs));
            initPcDropdown();
            changeTargetPC();
        }

        let touchpadMode = false;
        let dragging = false;
        let lastX = 0, lastY = 0;

        function updateStreamFeed() {
            let monitor = document.getElementById('monitorSelect').value;
            let scale = document.getElementById('qualitySelect').value;
            document.getElementById('stream').src = `${baseUrl}/video_feed?monitor=${monitor}&scale=${scale}`;
        }

        function updateStreamConfig() {
            updateStreamFeed();
        }

        updateStreamFeed();

        // Funkce pro celou obrazovku
        function toggleFullscreen() {
            let img = document.getElementById('stream');
            if (!document.fullscreenElement) {
                if (img.requestFullscreen) {
                    img.requestFullscreen();
                } else if (img.webkitRequestFullscreen) {
                    img.webkitRequestFullscreen();
                } else if (img.msRequestFullscreen) {
                    img.msRequestFullscreen();
                }
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                }
            }
        }

        function cmd(action) { fetch(baseUrl + '/cmd?action=' + action); }
        
        function confirmAndCmd(action, msg) {
            if(confirm(msg)) { cmd(action); }
        }

        function toggleTouchpadMode() {
            touchpadMode = !touchpadMode;
            let btn = document.getElementById('modeBtn');
            let bar = document.getElementById('touchpadBar');
            let area = document.getElementById('touchpadArea');
            if (touchpadMode) {
                btn.innerText = "Mode: Touchpad";
                btn.style.background = "#060";
                bar.style.display = "flex";
                area.style.display = "flex";
            } else {
                btn.innerText = "Mode: Kliknutí";
                btn.style.background = "#262";
                bar.style.display = "none";
                area.style.display = "none";
            }
        }

        const touchpadArea = document.getElementById('touchpadArea');

        touchpadArea.addEventListener('pointerdown', (e) => {
            lastX = e.clientX;
            lastY = e.clientY;
            touchpadArea.setPointerCapture(e.pointerId);
        });

        touchpadArea.addEventListener('pointermove', (e) => {
            if (e.buttons === 0) return;
            let dx = e.clientX - lastX;
            let dy = e.clientY - lastY;
            lastX = e.clientX;
            lastY = e.clientY;
            
            fetch(`${baseUrl}/move_rel?dx=${dx}&dy=${dy}`);
        });

        function handleStreamClick(event) {
            if (touchpadMode) return;
            var rect = event.target.getBoundingClientRect();
            var x = (event.clientX - rect.left) / rect.width;
            var y = (event.clientY - rect.top) / rect.height;
            let monitor = document.getElementById('monitorSelect').value;
            fetch(`${baseUrl}/click?x=${x}&y=${y}&monitor=${monitor}`);
        }

        function toggleDrag() {
            dragging = !dragging;
            document.getElementById('dragBtn').style.background = dragging ? '#f00' : '#444';
            cmd(dragging ? 'mouse_hold' : 'mouse_release');
        }

        function sendClip() { 
            fetch(baseUrl + '/set_clip?text=' + encodeURIComponent(document.getElementById('clipText').value)); 
        }

        function sendCustomShortcut() {
            let keys = document.getElementById('customShortcut').value;
            fetch(baseUrl + '/shortcut?keys=' + encodeURIComponent(keys));
        }

        function uploadFile() {
            let file = document.getElementById('fileInput').files[0];
            let formData = new FormData(); formData.append('file', file);
            fetch(baseUrl + '/upload', {method: 'POST', body: formData});
        }

        function uploadCode() {
            let file = document.getElementById('codeUploadInput').files[0];
            if (!file) return;
            if (!confirm('Opravdu nahrát nový kód a restartovat server na dálku?')) return;
            let formData = new FormData(); formData.append('file', file);
            fetch(baseUrl + '/update_script', {method: 'POST', body: formData})
                .then(r => r.text())
                .then(msg => {
                    alert(msg);
                    setTimeout(() => { location.reload(); }, 3000);
                });
        }

        function startVoice() {
            let rec = new webkitSpeechRecognition(); rec.lang = 'cs-CZ';
            rec.onresult = (e) => { fetch(baseUrl + '/type?text=' + encodeURIComponent(e.results[0][0].transcript)); };
            rec.start();
        }

        setInterval(() => {
            fetch(baseUrl + '/stats').then(r => r.json()).then(data => {
                document.getElementById('stats').innerText = `CPU: ${data.cpu}% | RAM: ${data.ram}%`;
            });
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
@requires_auth
def index(): return render_template_string(HTML_PAGE)

@app.route('/raw_code')
def raw_code():
    return send_file(__file__, mimetype='text/plain')

@app.route('/stats')
@requires_auth
def stats(): return jsonify({'cpu': psutil.cpu_percent(), 'ram': psutil.virtual_memory().percent})

@app.route('/set_clip')
@requires_auth
def set_clip():
    pyperclip.copy(request.args.get('text'))
    return "OK"

@app.route('/shortcut')
@requires_auth
def shortcut():
    keys_str = request.args.get('keys', '')
    if keys_str:
        keys_list = [k.strip() for k in keys_str.split(',')]
        pyautogui.hotkey(*keys_list)
    return "OK"

@app.route('/upload', methods=['POST'])
@requires_auth
def upload_file():
    file = request.files['file']
    filename = secure_filename(file.filename)
    file.save(filename)
    os.startfile(filename)
    return "OK"

@app.route('/update_script', methods=['POST'])
@requires_auth
def update_script():
    if 'file' not in request.files:
        return "Žádný soubor", 400
    file = request.files['file']
    if file.filename.endswith('.py'):
        script_path = os.path.abspath(__file__)
        file.save(script_path)
        
        def restart_server():
            time.sleep(1)
            python = sys.executable
            os.execl(python, python, *sys.argv)
            
        threading.Thread(target=restart_server).daemon = True
        return "Skript byl aktualizován. Server se restartuje..."
    return "Pouze .py soubory jsou povoleny", 400

@app.route('/cmd')
@requires_auth
def cmd():
    action = request.args.get('action')
    
    # Myš a okna
    if action == 'right_click': pyautogui.rightClick()
    elif action == 'scroll_up': pyautogui.scroll(300)
    elif action == 'scroll_down': pyautogui.scroll(-300)
    elif action == 'mouse_hold': pyautogui.mouseDown()
    elif action == 'mouse_release': pyautogui.mouseUp()
    
    # Média a Hlasitost
    elif action == 'vol_up': pyautogui.press('volumeup')
    elif action == 'vol_down': pyautogui.press('volumedown')
    elif action == 'vol_mute': pyautogui.press('volumemute')
    elif action == 'media_play': pyautogui.press('playpause')
    elif action == 'media_next': pyautogui.press('nexttrack')
    elif action == 'media_prev': pyautogui.press('prevtrack')
    
    # Speciální klávesy
    elif action == 'key_enter': pyautogui.press('enter')
    elif action == 'key_backspace': pyautogui.press('backspace')
    elif action == 'key_space': pyautogui.press('space')
    elif action == 'key_tab': pyautogui.press('tab')
    elif action == 'key_esc': pyautogui.press('escape')
    elif action == 'key_alttab': pyautogui.hotkey('alt', 'tab')
    elif action == 'key_wind': pyautogui.hotkey('win', 'd')

    # Spouštěče aplikací
    elif action == 'launch_chrome': os.system('start chrome')
    elif action == 'launch_spotify': os.system('start spotify')
    elif action == 'launch_steam': os.system('start steam')
    elif action == 'launch_calc': os.system('start calc')
    elif action == 'launch_notepad': os.system('start notepad')
    elif action == 'kill_chrome':
        for p in psutil.process_iter():
            if 'chrome' in p.name().lower(): p.kill()
            
    # Napájení
    elif action == 'lock_pc': ctypes.windll.user32.LockWorkStation()
    elif action == 'sleep_pc': os.system('rundll32.exe powrProf.dll,SetSuspendState Sleep')
    elif action == 'restart_pc': os.system('shutdown /r /t 0')
    elif action == 'shutdown_pc': os.system('shutdown /s /t 0')
    
    elif action == 'shutdown_server':
        func = request.environ.get('werkzeug.server.shutdown')
        if func: func()
    return "OK"

@app.route('/click')
@requires_auth
def click():
    x, y = float(request.args.get('x')), float(request.args.get('y'))
    monitor_idx = int(request.args.get('monitor', 1))
    with mss.mss() as sct:
        if monitor_idx < len(sct.monitors):
            mon = sct.monitors[monitor_idx]
            abs_x = mon["left"] + int(x * mon["width"])
            abs_y = mon["top"] + int(y * mon["height"])
            pyautogui.click(abs_x, abs_y)
        else:
            sw, sh = pyautogui.size()
            pyautogui.click(int(x * sw), int(y * sh))
    return "OK"

@app.route('/move_rel')
@requires_auth
def move_rel():
    dx = float(request.args.get('dx', 0))
    dy = float(request.args.get('dy', 0))
    pyautogui.moveRel(int(dx * 1.5), int(dy * 1.5))
    return "OK"

@app.route('/type')
@requires_auth
def type_text():
    pyautogui.write(request.args.get('text'))
    return "OK"

def generate_frames(monitor_idx, scale_factor):
    with mss.mss() as sct:
        while True:
            try:
                idx = monitor_idx if monitor_idx < len(sct.monitors) else 1
                monitor = sct.monitors[idx]
                
                img = np.frombuffer(sct.grab(monitor).raw, dtype='uint8').reshape((monitor['height'], monitor['width'], 4))
                fx = float(scale_factor)
                img = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR), (0,0), fx=fx, fy=fx)
                _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            except: 
                time.sleep(1)

@app.route('/video_feed')
@requires_auth
def video_feed():
    monitor = int(request.args.get('monitor', 1))
    scale = request.args.get('scale', '0.4')
    return Response(generate_frames(monitor, scale), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
from flask import Flask, request, jsonify, render_template_string
from model_core import evaluate_from_unity, adjust_difficulty_dda
import pickle
import json
import csv
import pandas as pd
from datetime import datetime
import os

import requests
import base64

GAS_URL = "https://script.google.com/macros/s/AKfycbwxasW97p-s7H6Rtht0U0QybuRo36EAFR8SI-5Edq4hQ0w5bAqyyHspDLl9WJ4ykCpC/exec"

app = Flask(__name__)

# --- 1. 殭屍基礎數值定義 (與 Unity 初始設定同步) ---
BASE_STATS = {
    "HP": 100.0,
    "ATK": 10.0,
    "DET": 20.0,
    "SPD": 2.5
}

# --- 2. 載入模型參數 ---
try:
    with open("P_Strong.pkl", "rb") as f:
        P_Strong = pickle.load(f)
    with open("P_Weak.pkl", "rb") as f:
        P_Weak = pickle.load(f)
    print("✅ 成功載入模型參數。")
except FileNotFoundError:
    print("⚠️ 找不到模型檔案，使用預設安全邊界。")
    P_Strong = {"HP_Mult": 1.4, "ATK_Mult": 1.2, "Det_Range": 1.1, "Move_Speed": 1.2}
    P_Weak = {"HP_Mult": 0.8, "ATK_Mult": 0.8, "Det_Range": 0.9, "Move_Speed": 0.9}

# --- 3. 全域狀態管理與 CSV 標題初始化 ---
PLAYER_SESSIONS = {}
LOG_FILE = "dda_experiment_logs.csv"
FINAL_RESULT_FILE = "final_experiment_results.csv"


def init_csv_files():
    log_header = ["時間", "玩家ID", "模式", "場景", "狀態", "K/D值", "HP倍率", "ATK倍率", "DET倍率", "SPD倍率",
                  "HP實值", "ATK實值", "DET實值", "SPD實值", "動作"]
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(log_header)

    final_header = ["紀錄時間", "玩家ID", "模式", "總造成傷害", "總受到傷害", "擊殺數", "死亡數", "通關時間",
                    "結果狀態"]
    if not os.path.exists(FINAL_RESULT_FILE) or os.path.getsize(FINAL_RESULT_FILE) == 0:
        with open(FINAL_RESULT_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(final_header)


init_csv_files()

# --- 4. 監控面板 HTML 模板 (恢復完整欄位版) ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8"><title>DDA 實驗監控中心 v4.8</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .chart-container { position: relative; height: 350px; width: 100%; }
        select { background-color: #1f2937; color: white; border: 1px solid #4b5563; padding: 0.5rem; border-radius: 0.5rem; }
        .stat-card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(8px); border: 1px solid #334155; }
    </style>
</head>
<body class="bg-slate-900 text-slate-100 p-6 font-sans">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center mb-6 border-b border-slate-700 pb-4">
            <div>
                <h1 class="text-3xl font-bold text-cyan-400">DDA 數據監控中心</h1>
                <p class="text-slate-400 text-sm mt-1">完整功能恢復：包含實時指標、最終總結與自動追蹤</p>
            </div>
            <select id="playerSelect" onchange="changePlayer()" class="bg-slate-800">
                <option value="latest">--- 自動追蹤最新受試者 ---</option>
            </select>
        </header>

        <!-- 1. 頂部狀態指標 (恢復欄位) -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div class="stat-card p-4 rounded-xl text-center">
                <p class="text-slate-500 text-[10px] uppercase font-bold">當前玩家 ID</p>
                <h2 id="current-player" class="text-lg text-cyan-400 font-bold mt-1 truncate">N/A</h2>
            </div>
            <div class="stat-card p-4 rounded-xl text-center">
                <p class="text-slate-500 text-[10px] uppercase font-bold">當前 K/D 比值</p>
                <h2 id="kd-display" class="text-lg text-white font-bold mt-1">0.00</h2>
            </div>
            <div class="stat-card p-4 rounded-xl text-center">
                <p class="text-slate-500 text-[10px] uppercase font-bold">冷靜期 (恢復中)</p>
                <h2 id="recovery-steps" class="text-lg text-amber-400 font-bold mt-1">0</h2>
            </div>
            <div class="stat-card p-4 rounded-xl text-center">
                <p class="text-slate-500 text-[10px] uppercase font-bold">受試者狀態</p>
                <h2 id="player-status" class="text-xs text-emerald-400 font-bold mt-2">-</h2>
            </div>
        </div>

        <!-- 2. 🏆 最終結果總結 -->
        <div id="finalResultCard" class="hidden mb-6 bg-indigo-900/40 border border-indigo-500/50 rounded-2xl p-6 shadow-2xl">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold text-indigo-300">🏆 本局實驗最終結果總結</h2>
                <span id="res-status-tag" class="px-3 py-1 bg-green-900/50 text-green-400 text-xs rounded-full border border-green-500">Completed</span>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                <div class="bg-slate-800/50 p-3 rounded-lg"> <p class="text-[10px] text-slate-500 uppercase">總擊殺</p> <p id="res-kills" class="text-xl font-bold">--</p> </div>
                <div class="bg-slate-800/50 p-3 rounded-lg"> <p class="text-[10px] text-slate-500 uppercase">總死亡</p> <p id="res-deaths" class="text-xl font-bold">--</p> </div>
                <div class="bg-slate-800/50 p-3 rounded-lg"> <p class="text-[10px] text-slate-500 uppercase">輸出傷害</p> <p id="res-dmg-out" class="text-xl font-bold">--</p> </div>
                <div class="bg-slate-800/50 p-3 rounded-lg"> <p class="text-[10px] text-slate-500 uppercase">受傷數值</p> <p id="res-dmg-in" class="text-xl font-bold">--</p> </div>
                <div class="bg-slate-800/50 p-3 rounded-lg border border-cyan-500/30"> <p class="text-[10px] text-cyan-500 uppercase">通關耗時</p> <p id="res-time" class="text-xl font-bold text-cyan-400">--</p> </div>
            </div>
        </div>

        <!-- 3. 殭屍屬性詳情 (恢復倍率與實值) -->
        <div class="bg-slate-800/80 p-5 rounded-2xl border border-slate-700 shadow-xl mb-6">
            <div class="flex justify-between items-center mb-4 border-b border-slate-700 pb-2">
                <h3 class="text-sm font-bold text-indigo-400">殭屍能力詳情 (基礎換算實值)</h3>
                <h2 id="last-action" class="text-xs text-amber-400 font-bold">-</h2>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-slate-900/50 p-3 rounded-lg text-center"> 
                    <p class="text-[10px] text-slate-500">血量 (HP)</p> 
                    <h4 id="real-hp" class="text-xl font-mono text-red-400">--</h4>
                    <p id="mult-hp" class="text-[9px] text-slate-600">倍率: --</p>
                </div>
                <div class="bg-slate-900/50 p-3 rounded-lg text-center"> 
                    <p class="text-[10px] text-slate-500">攻擊 (ATK)</p> 
                    <h4 id="real-atk" class="text-xl font-mono text-amber-400">--</h4>
                    <p id="mult-atk" class="text-[9px] text-slate-600">倍率: --</p>
                </div>
                <div class="bg-slate-900/50 p-3 rounded-lg text-center"> 
                    <p class="text-[10px] text-slate-500">偵測 (DET)</p> 
                    <h4 id="real-det" class="text-xl font-mono text-purple-400">--</h4>
                    <p id="mult-det" class="text-[9px] text-slate-600">倍率: --</p>
                </div>
                <div class="bg-slate-900/50 p-3 rounded-lg text-center"> 
                    <p class="text-[10px] text-slate-500">速度 (SPD)</p> 
                    <h4 id="real-spd" class="text-xl font-mono text-emerald-400">--</h4>
                    <p id="mult-spd" class="text-[9px] text-slate-600">倍率: --</p>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-slate-800 p-6 rounded-2xl h-[400px] shadow-xl"><canvas id="kdChart"></canvas></div>
            <div class="bg-slate-800 p-6 rounded-2xl h-[400px] shadow-xl"><canvas id="paramChart"></canvas></div>
        </div>
    </div>

    <script>
        let selectedPlayer = 'latest';
        const BASE = {{ BASE_STATS | tojson }};
        const kdChart = new Chart(document.getElementById('kdChart').getContext('2d'), { type: 'line', data: { labels: [], datasets: [{ label: 'K/D Ratio', borderColor: '#22d3ee', data: [], tension: 0.4 }] }, options: { responsive: true, maintainAspectRatio: false }});
        const paramChart = new Chart(document.getElementById('paramChart').getContext('2d'), { type: 'line', data: { labels: [], datasets: [
            { label: 'HP', borderColor: '#f87171', data: [], borderWidth: 3 },
            { label: 'ATK', borderColor: '#fbbf24', data: [], borderWidth: 2, borderDash: [5, 5] },
            { label: 'DET', borderColor: '#a78bfa', data: [], borderWidth: 2 },
            { label: 'SPD', borderColor: '#34d399', data: [], borderWidth: 3, borderDash: [2, 2] }
        ]}, options: { responsive: true, maintainAspectRatio: false, scales: { y: { min: 0.6, max: 1.6 }}}});

        async function updateDashboard() {
            try {
                const res = await fetch('/get_history');
                const allData = await res.json();
                const players = Object.keys(allData);

                const sortedPlayers = players.sort((a, b) => allData[a].last_updated - allData[b].last_updated);

                const select = document.getElementById('playerSelect');
                if(sortedPlayers.length !== (select.options.length - 1)) {
                    select.innerHTML = '<option value="latest">--- 自動追蹤最新 ---</option>';
                    sortedPlayers.forEach(p => { select.innerHTML += `<option value="${p}">${p}</option>`; });
                    select.value = selectedPlayer;
                }

                if(sortedPlayers.length > 0) {
                    const targetID = (selectedPlayer === 'latest') ? sortedPlayers[sortedPlayers.length - 1] : selectedPlayer;
                    const session = allData[targetID];
                    document.getElementById('current-player').innerText = targetID;

                    // A. 更新指標卡片
                    document.getElementById('recovery-steps').innerText = session.recovery_counter || 0;

                    // B. 更新總結卡片
                    if(session.final_result) {
                        document.getElementById('finalResultCard').classList.remove('hidden');
                        const f = session.final_result;
                        document.getElementById('res-kills').innerText = f.kills || 0;
                        document.getElementById('res-deaths').innerText = f.deaths || 0;
                        document.getElementById('res-dmg-out').innerText = Math.round(f.totalDamage || 0);
                        document.getElementById('res-dmg-in').innerText = Math.round(f.damageTaken || 0);
                        document.getElementById('res-time').innerText = (f.completionTime || 0).toFixed(1) + 's';
                    } else { document.getElementById('finalResultCard').classList.add('hidden'); }

                    // C. 更新歷史與實值
                    if(session.history.length > 0) {
                        const last = session.history[session.history.length - 1];
                        // 改用新的大寫變數名稱
                        document.getElementById('kd-display').innerText = last.KD_Ratio;
                        document.getElementById('player-status').innerText = last.Status;
                        document.getElementById('last-action').innerText = last.Action;

                        // 因為後端已經算好 Real_HP 等實值了，直接拿來顯示即可
                        document.getElementById('real-hp').innerText = last.Real_HP.toFixed(1);
                        document.getElementById('mult-hp').innerText = `倍率: ${last.HP_Mult.toFixed(2)}x`;
                        document.getElementById('real-atk').innerText = last.Real_ATK.toFixed(1);
                        document.getElementById('mult-atk').innerText = `倍率: ${last.ATK_Mult.toFixed(2)}x`;
                        document.getElementById('real-det').innerText = last.Real_DET.toFixed(1);
                        document.getElementById('mult-det').innerText = `倍率: ${last.DET_Mult.toFixed(2)}x`;
                        document.getElementById('real-spd').innerText = last.Real_SPD.toFixed(2);
                        document.getElementById('mult-spd').innerText = `倍率: ${last.SPD_Mult.toFixed(2)}x`;

                        // 更新圖表：改對應 KD_Ratio, HP_Mult 等新變數
                        kdChart.data.labels = session.history.map((_, i) => i);
                        kdChart.data.datasets[0].data = session.history.map(h => h.KD_Ratio);
                        kdChart.update('none');
                        
                        paramChart.data.labels = session.history.map((_, i) => i);
                        paramChart.data.datasets[0].data = session.history.map(h => h.HP_Mult);
                        paramChart.data.datasets[1].data = session.history.map(h => h.ATK_Mult);
                        paramChart.data.datasets[2].data = session.history.map(h => h.DET_Mult);
                        paramChart.data.datasets[3].data = session.history.map(h => h.SPD_Mult);
                        paramChart.update('none');
                    }
                }
            } catch (e) { console.error(e); }
        }
        setInterval(updateDashboard, 2000);
        function changePlayer() { selectedPlayer = document.getElementById('playerSelect').value; updateDashboard(); }
    </script>
</body>
</html>
"""


# --- 5. 路由處理邏輯 ---

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML, BASE_STATS=BASE_STATS)


@app.route('/get_history')
def get_history_api():
    return jsonify(PLAYER_SESSIONS)


@app.route("/adjust_difficulty", methods=["POST"])
def adjust_difficulty():
    global PLAYER_SESSIONS
    data = request.get_json()
    player_id = (data.get("player_id") or data.get("playerID") or "Subject").strip()
    status = data.get("status", "Alive")
    scene = data.get("scene_name", "Unknown")
    mode = str(data.get("mode", "0"))
    game_time = data.get("game_time", 0)

    if player_id not in PLAYER_SESSIONS:
        PLAYER_SESSIONS[player_id] = {
            "params": {"HP_Mult": 1.0, "ATK_Mult": 1.0, "Det_Range": 1.0, "Move_Speed": 1.0},
            "history": [], "has_calibrated": False, "recovery_counter": 0,
            "final_result": None, "mode": mode, "last_updated": datetime.now().timestamp()
        }

    session = PLAYER_SESSIONS[player_id]
    session["last_updated"] = datetime.now().timestamp()
    session["mode"] = mode
    is_tut = (scene == "Tutorial")

    # 死亡與恢復期邏輯
    if mode == "0":
        session["params"] = {"HP_Mult": 1.0, "ATK_Mult": 1.0, "Det_Range": 1.0, "Move_Speed": 1.0}
        action = "Monitoring (Control)"
    else:
        if status == "Dead":
            for key in session["params"]:
                session["params"][key] = session["params"][key] + (P_Weak[key] - session["params"][key]) * 0.7
            action = "Emergency Down (Death)"
            session["recovery_counter"] = 4
        else:
            if session["recovery_counter"] > 0:
                new_params, action = adjust_difficulty_dda(session["params"], data, P_Strong, P_Weak, is_tut, False)
                if "Up" in action:
                    for key in session["params"]:
                        session["params"][key] += (new_params[key] - session["params"][key]) * 0.3
                    action += " (Restricted)"
                else:
                    session["params"] = new_params
                session["recovery_counter"] -= 1
            else:
                is_first = (not session["has_calibrated"] and game_time > 2 and not is_tut)
                if is_first: session["has_calibrated"] = True
                new_params, action = adjust_difficulty_dda(session["params"], data, P_Strong, P_Weak, is_tut, is_first)
                session["params"] = new_params

    # 數據日誌記錄
    kill = data.get('kill_count', 0)
    death = data.get('death_count', 0)
    kd = kill / (death if death > 0 else 0.5)
    session["history"].append({
        "Time": datetime.now().strftime("%H:%M:%S"),
        "Player_ID": player_id,
        "Mode": mode,
        "Scene": scene,
        "Status": status,
        "KD_Ratio": round(kd, 2),
        "HP_Mult": round(session["params"]["HP_Mult"], 2),
        "ATK_Mult": round(session["params"]["ATK_Mult"], 2),
        "DET_Mult": round(session["params"]["Det_Range"], 2),
        "SPD_Mult": round(session["params"]["Move_Speed"], 2),
        "Real_HP": round(session["params"]["HP_Mult"] * BASE_STATS['HP'], 1),
        "Real_ATK": round(session["params"]["ATK_Mult"] * BASE_STATS['ATK'], 1),
        "Real_DET": round(session["params"]["Det_Range"] * BASE_STATS['DET'], 1),
        "Real_SPD": round(session["params"]["Move_Speed"] * BASE_STATS['SPD'], 2),
        "Action": action
    })
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([datetime.now().strftime("%H:%M:%S"), player_id, mode, scene, status, f"{kd:.2f}",
                                f"{session['params']['HP_Mult']:.2f}", f"{session['params']['ATK_Mult']:.2f}",
                                f"{session['params']['Det_Range']:.2f}", f"{session['params']['Move_Speed']:.2f}",
                                f"{session['params']['HP_Mult'] * BASE_STATS['HP']:.1f}",
                                f"{session['params']['ATK_Mult'] * BASE_STATS['ATK']:.1f}",
                                f"{session['params']['Det_Range'] * BASE_STATS['DET']:.1f}",
                                f"{session['params']['Move_Speed'] * BASE_STATS['SPD']:.2f}", action])

    return jsonify({"adjusted_params": session["params"], "adjustment_action": action})


@app.route("/submit_final_result", methods=["POST"])
def submit_final_result():
    global PLAYER_SESSIONS
    data = request.get_json()
    player_id = (data.get("player_id") or data.get("playerID") or "Unknown").strip()
    mode = str(data.get("mode", "N/A"))

    if player_id in PLAYER_SESSIONS:
        PLAYER_SESSIONS[player_id]["final_result"] = data
        PLAYER_SESSIONS[player_id]["last_updated"] = datetime.now().timestamp()
        if mode == "Game" or mode == "N/A":
            mode = PLAYER_SESSIONS[player_id].get("mode", mode)

    # 1. 定義要寫入的結算數據陣列 (這樣本地端與雲端才能共用這筆資料)
    row_data = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        player_id,
        mode,
        data.get("totalDamage", 0),
        data.get("damageTaken", 0),
        data.get("kills", 0),
        data.get("deaths", 0),
        data.get("completionTime", 0),
        data.get("result")
    ]

    # 2. 寫入全局的 final_experiment_results.csv (本地備份)
    with open(FINAL_RESULT_FILE, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(row_data)

    # ✨ 呼叫雲端上傳 1：將結算數據寫入 Google 試算表
    append_summary_to_sheet(row_data)

    # ---------------------------------------------------------
    # 3. 產出該玩家專屬的完整 DDA 歷程 CSV 並上傳
    # ---------------------------------------------------------
    if player_id in PLAYER_SESSIONS and len(PLAYER_SESSIONS[player_id]["history"]) > 0:
        try:
            # 取出該玩家的歷史紀錄並轉為 DataFrame
            history_data = PLAYER_SESSIONS[player_id]["history"]
            df = pd.DataFrame(history_data)

            # 建立獨立存放的資料夾
            backup_dir = "Local_Player_Data"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)

            # 生成獨一無二的檔名：時間戳記 + 玩家ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Player_{player_id}_Mode{mode}_{timestamp}.csv"
            filepath = os.path.join(backup_dir, filename)

            # 輸出 CSV (使用 utf-8-sig 避免 Excel 開啟時中文亂碼)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"✅ 專屬數據已匯出：{filepath}")

            # ✨ 呼叫雲端上傳 2：將專屬 CSV 檔案傳送至 Google Drive
            upload_csv_to_drive(filepath)

        except Exception as e:
            print(f"❌ 產出或上傳專屬 CSV 時發生錯誤：{e}")

    return jsonify({"status": "success", "message": "結算數據已記錄，專屬 CSV 已生成並上傳"})
def upload_csv_to_drive(filepath):
    try:
        with open(filepath, "rb") as f:
            file_content = base64.b64encode(f.read()).decode("utf-8")

        filename = os.path.basename(filepath)
        payload = {
            "type": "file",
            "filename": filename,
            "fileContent": file_content
        }

        print(f"🚀 準備上傳 {filename} 至 Google Drive...")
        res = requests.post(GAS_URL, json=payload)
        print(f"☁️ 雲端回應: {res.json().get('message', '未知回應')}")

    except Exception as e:
        print(f"❌ 上傳 CSV 失敗: {e}")


def append_summary_to_sheet(row_data):
    try:
        payload = {
            "type": "summary",
            "rowData": row_data
        }
        print(f"🚀 準備將結算數據寫入 Google Sheets...")
        res = requests.post(GAS_URL, json=payload)
        print(f"☁️ 雲端回應: {res.json().get('message', '未知回應')}")
    except Exception as e:
        print(f"❌ 寫入試算表失敗: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
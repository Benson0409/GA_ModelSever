from flask import Flask, request, jsonify, render_template_string
from model_core import evaluate_from_unity, adjust_difficulty_dda
import pickle
import json
import csv
from datetime import datetime
import os

app = Flask(__name__)

# --- 1. 載入模型參數 (⚠️ 建議邊界：HP[0.8, 1.3], ATK[0.8, 1.3], DET/SPD[0.9, 1.1]) ---
try:
    with open("P_Strong.pkl", "rb") as f:
        P_Strong = pickle.load(f)
    with open("P_Weak.pkl", "rb") as f:
        P_Weak = pickle.load(f)
    print("✅ 成功載入模型參數。")
except FileNotFoundError:
    print("❌ 找不到模型檔案，將使用極度保守的預設值。")
    # 根據你的回饋，限制偵測與速度在 +/- 10% 範圍內，防止瞬移
    P_Strong = {"HP_Mult": 1.3, "ATK_Mult": 1.3, "Det_Range": 1.1, "Move_Speed": 1.1}
    P_Weak = {"HP_Mult": 0.8, "ATK_Mult": 0.8, "Det_Range": 0.9, "Move_Speed": 0.9}

# --- 2. 全域狀態管理與 CSV 標題強制校正 ---
PLAYER_SESSIONS = {}
LOG_FILE = "dda_experiment_logs.csv"


def init_csv_header():
    header = ["時間", "玩家ID", "模式", "場景", "狀態", "K/D值", "評估分數", "血量倍率", "攻擊倍率", "偵測範圍",
              "移動速度", "動作"]
    file_exists = os.path.exists(LOG_FILE)
    if not file_exists or os.path.getsize(LOG_FILE) == 0:
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
    else:
        # 檢查第一行是否包含標題關鍵字
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if "時間" not in first_line:
                content = f.read()
                with open(LOG_FILE, 'w', newline='', encoding='utf-8') as fw:
                    writer = csv.writer(fw)
                    writer.writerow(header)
                    fw.write(first_line + content)


init_csv_header()

# --- 3. 實時監控面板 (Dashboard HTML v2.8 - 強制四線顯示) ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>DDA AI 實驗監控中心 v2.8</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .chart-container { position: relative; height: 400px; width: 100%; }
        select { background-color: #1f2937; color: white; border: 1px solid #4b5563; padding: 0.5rem; border-radius: 0.5rem; }
    </style>
</head>
<body class="bg-slate-900 text-slate-100 p-6 font-sans">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center mb-6 border-b border-slate-700 pb-4">
            <div>
                <h1 class="text-3xl font-bold text-cyan-400 tracking-tight">DDA 實驗管理平台</h1>
                <p class="text-slate-400 text-sm mt-1">即時監控：血量、攻擊、偵測、速度 (全量顯示模式)</p>
            </div>
            <div class="flex items-center gap-4">
                <div class="text-right">
                    <p class="text-[10px] text-slate-500 uppercase font-bold">受試者選擇</p>
                    <select id="playerSelect" onchange="changePlayer()">
                        <option value="latest">--- 自動追蹤最新 ---</option>
                    </select>
                </div>
                <div id="status-tag" class="px-4 py-2 bg-emerald-900/50 text-emerald-400 rounded-lg text-xs font-bold border border-emerald-500/50 animate-pulse">系統連線中</div>
            </div>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 text-center">
            <div class="bg-slate-800/50 p-4 rounded-xl border border-slate-700 shadow-xl">
                <p class="text-slate-500 text-[10px] uppercase font-bold">累計樣本</p>
                <h2 id="player-count" class="text-3xl font-mono text-white mt-1">0</h2>
            </div>
            <div class="bg-slate-800/50 p-4 rounded-xl border border-slate-700 shadow-xl">
                <p class="text-slate-500 text-[10px] uppercase font-bold">當前檢視 ID</p>
                <h2 id="current-player" class="text-xl text-cyan-400 font-bold mt-1 truncate">N/A</h2>
            </div>
            <div class="bg-slate-800/50 p-4 rounded-xl border border-slate-700 shadow-xl">
                <p class="text-slate-500 text-[10px] uppercase font-bold">最後調整行動</p>
                <h2 id="last-action" class="text-sm text-amber-400 font-bold mt-2">-</h2>
            </div>
            <div class="bg-slate-800/50 p-4 rounded-xl border border-slate-700 shadow-xl">
                <p class="text-slate-500 text-[10px] uppercase font-bold">最新回傳狀態</p>
                <h2 id="player-status" class="text-sm text-emerald-400 font-bold mt-2">-</h2>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-slate-800/80 p-6 rounded-2xl border border-slate-700 shadow-2xl">
                <h3 class="text-sm font-bold text-slate-300 mb-4 flex items-center">
                    <span class="w-2 h-2 bg-cyan-400 rounded-full mr-2"></span> 玩家 K/D 表現
                </h3>
                <div class="chart-container"><canvas id="kdChart"></canvas></div>
            </div>
            <div class="bg-slate-800/80 p-6 rounded-2xl border border-slate-700 shadow-2xl">
                <h3 class="text-sm font-bold text-slate-300 mb-4 flex items-center">
                    <span class="w-2 h-2 bg-indigo-400 rounded-full mr-2"></span> 殭屍屬性演化 (HP/ATK/DET/SPD)
                </h3>
                <div class="chart-container"><canvas id="paramChart"></canvas></div>
            </div>
        </div>
    </div>

    <script>
        let selectedPlayer = 'latest';
        const kdCtx = document.getElementById('kdChart').getContext('2d');
        const paramCtx = document.getElementById('paramChart').getContext('2d');

        const kdChart = new Chart(kdCtx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'K/D Ratio', borderColor: '#22d3ee', backgroundColor: 'rgba(34, 211, 238, 0.1)', data: [], tension: 0.4, fill: true, pointRadius: 0 }] },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, grid: { color: '#334155' } }, x: { grid: { display: false } } } }
        });

        const paramChart = new Chart(paramCtx, {
            type: 'line',
            data: { 
                labels: [], 
                datasets: [
                    { label: '血量 (HP)', borderColor: '#f87171', data: [], tension: 0.3, pointRadius: 2, borderWidth: 2 },
                    { label: '攻擊 (ATK)', borderColor: '#fbbf24', data: [], tension: 0.3, pointRadius: 2, borderWidth: 2 },
                    { label: '偵測 (DET)', borderColor: '#a78bfa', data: [], tension: 0.3, pointRadius: 2, borderWidth: 2 },
                    { label: '速度 (SPD)', borderColor: '#34d399', data: [], tension: 0.3, pointRadius: 2, borderWidth: 2 }
                ] 
            },
            options: { 
                responsive: true, maintainAspectRatio: false, 
                scales: { 
                    y: { min: 0.7, max: 1.5, grid: { color: '#334155' } },
                    x: { grid: { display: false } }
                },
                plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 }, usePointStyle: true, padding: 20 } } }
            }
        });

        function changePlayer() {
            selectedPlayer = document.getElementById('playerSelect').value;
            updateDashboard(true);
        }

        async function updateDashboard(forceRefresh = false) {
            try {
                const res = await fetch('/get_history');
                const allData = await res.json();
                const players = Object.keys(allData);

                const select = document.getElementById('playerSelect');
                if(players.length > (select.options.length - 1)) {
                    select.innerHTML = '<option value=\"latest\">--- 自動追蹤最新 ---</option>';
                    players.forEach(p => {
                        let opt = document.createElement('option');
                        opt.value = p; opt.innerHTML = p;
                        select.appendChild(opt);
                    });
                    select.value = selectedPlayer;
                }

                document.getElementById('player-count').innerText = players.length;

                if(players.length > 0) {
                    const targetID = (selectedPlayer === 'latest') ? players[players.length - 1] : selectedPlayer;
                    document.getElementById('current-player').innerText = targetID;

                    const history = allData[targetID].history;
                    if(history.length > 0) {
                        const lastEntry = history[history.length - 1];
                        document.getElementById('last-action').innerText = lastEntry.action;
                        document.getElementById('player-status').innerText = lastEntry.status;

                        const labels = history.map((_, i) => i);
                        kdChart.data.labels = labels;
                        kdChart.data.datasets[0].data = history.map(h => h.kd);
                        kdChart.update('none');

                        paramChart.data.labels = labels;
                        // 明確映射四個屬性，解決曲線不出現問題
                        paramChart.data.datasets[0].data = history.map(h => h.hp);
                        paramChart.data.datasets[1].data = history.map(h => h.atk);
                        paramChart.data.datasets[2].data = history.map(h => h.det);
                        paramChart.data.datasets[3].data = history.map(h => h.spd);
                        paramChart.update('none');
                    }
                }
            } catch (e) { console.error(\"Update Error\", e); }
        }
        setInterval(() => updateDashboard(false), 2000);
    </script>
</body>
</html>
"""


# --- 4. 路由定義 ---

@app.route('/')
def dashboard_home():
    return render_template_string(DASHBOARD_HTML)


@app.route('/get_history')
def get_history_api():
    return jsonify(PLAYER_SESSIONS)


@app.route("/adjust_difficulty", methods=["POST"])
def adjust_difficulty():
    global PLAYER_SESSIONS
    data = request.get_json()
    if not data: return jsonify({"error": "No data"}), 400

    player_id = data.get("player_id", "Default_User")
    status = data.get("status", "Alive")
    scene = data.get("scene_name", "Unknown")
    mode = data.get("mode", "20s")

    if player_id not in PLAYER_SESSIONS:
        PLAYER_SESSIONS[player_id] = {
            "params": {"HP_Mult": 1.0, "ATK_Mult": 1.0, "Det_Range": 1.0, "Move_Speed": 1.0},
            "history": [], "has_calibrated": False
        }

    session = PLAYER_SESSIONS[player_id]
    is_tut = (scene == "Tutorial")
    is_first = False
    if not is_tut and not session["has_calibrated"]:
        is_first = True
        session["has_calibrated"] = True

    current_params_list = [session["params"]["HP_Mult"], session["params"]["ATK_Mult"],
                           session["params"]["Det_Range"], session["params"]["Move_Speed"]]

    score = evaluate_from_unity(current_params_list, data)

    # 狀態判斷：完全取消冷靜期，進入場景即刻介入
    if status == "Dead":
        # 死亡時強制使用較大的調整率，快速降難
        new_params, action = adjust_difficulty_dda(session["params"], data, P_Strong, P_Weak, False, True)
        action = "Emergency Down (Death)"
    else:
        # 正常 DDA
        new_params, action = adjust_difficulty_dda(session["params"], data, P_Strong, P_Weak, is_tut, is_first)

    if mode == "0":
        action = "Monitoring (No AI)"
    else:
        session["params"] = new_params

    kill, death = data.get('kill_count', 0), data.get('death_count', 1)
    kd_ratio = kill / (death if death > 0 else 0.5)

    # 更新歷史紀錄 (儲存 4 個屬性)
    session["history"].append({
        "kd": round(kd_ratio, 2),
        "hp": round(session["params"]["HP_Mult"], 2),
        "atk": round(session["params"]["ATK_Mult"], 2),
        "det": round(session["params"]["Det_Range"], 2),
        "spd": round(session["params"]["Move_Speed"], 2),
        "action": action, "status": status
    })

    # 寫入 CSV
    init_csv_header()
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%H:%M:%S"), player_id, mode, scene, status,
            f"{kd_ratio:.2f}", f"{score:.2f}",
            f"{session['params']['HP_Mult']:.2f}", f"{session['params']['ATK_Mult']:.2f}",
            f"{session['params']['Det_Range']:.2f}", f"{session['params']['Move_Speed']:.2f}",
            action
        ])

    return jsonify(
        {"adjusted_params": session["params"], "adjustment_action": action, "evaluation_score": score, "scene": scene})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
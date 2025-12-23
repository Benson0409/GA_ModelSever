from flask import Flask, request, jsonify, render_template_string
from model_core import evaluate_from_unity, adjust_difficulty_dda
import pickle
import json
import csv
from datetime import datetime
import os

app = Flask(__name__)

# --- 1. 殭屍基礎數值定義 ---
BASE_STATS = {
    "HP": 100.0,
    "ATK": 10.0,
    "DET": 20.0,
    "SPD": 2.5
}

# --- 2. 載入模型參數 (更新邊界) ---
try:
    with open("P_Strong.pkl", "rb") as f:
        P_Strong = pickle.load(f)
    with open("P_Weak.pkl", "rb") as f:
        P_Weak = pickle.load(f)
    print("✅ 成功載入模型參數。")
except FileNotFoundError:
    P_Strong = {"HP_Mult": 1.4, "ATK_Mult": 1.2, "Det_Range": 1.1, "Move_Speed": 1.2}
    P_Weak = {"HP_Mult": 0.8, "ATK_Mult": 0.8, "Det_Range": 0.9, "Move_Speed": 0.9}

# --- 3. 全域狀態管理 ---
PLAYER_SESSIONS = {}
LOG_FILE = "dda_experiment_logs.csv"


def init_csv_header():
    header = [
        "時間", "玩家ID", "模式", "場景", "狀態", "K/D值",
        "HP倍率", "ATK倍率", "DET倍率", "SPD倍率",
        "HP實值", "ATK實值", "DET實值", "SPD實值", "動作"
    ]
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)


init_csv_header()

# --- 4. 監控面板 HTML ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>DDA 監控中心 v3.6 (修正秒回升)</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .chart-container { position: relative; height: 380px; width: 100%; }
        select { background-color: #1f2937; color: white; border: 1px solid #4b5563; padding: 0.5rem; border-radius: 0.5rem; }
    </style>
</head>
<body class="bg-slate-900 text-slate-100 p-6 font-sans">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center mb-6 border-b border-slate-700 pb-4">
            <div>
                <h1 class="text-3xl font-bold text-cyan-400">DDA 實驗數據中心</h1>
                <p class="text-slate-400 text-sm mt-1">邏輯優化：死亡大幅降難 + 防止瞬間回溫</p>
            </div>
            <select id="playerSelect" onchange="changePlayer()">
                <option value="latest">--- 自動追蹤最新 ---</option>
            </select>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 text-center">
                <p class="text-slate-500 text-[10px] uppercase font-bold">當前玩家</p>
                <h2 id="current-player" class="text-lg text-cyan-400 font-bold mt-1 truncate">N/A</h2>
            </div>
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 text-center">
                <p class="text-slate-500 text-[10px] uppercase font-bold">K/D 比例</p>
                <h2 id="kd-display" class="text-lg text-white font-bold mt-1">0.00</h2>
            </div>
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 text-center">
                <p class="text-slate-500 text-[10px] uppercase font-bold">冷靜期步數</p>
                <h2 id="recovery-steps" class="text-lg text-amber-400 font-bold mt-1">0</h2>
            </div>
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700 text-center">
                <p class="text-slate-500 text-[10px] uppercase font-bold">目前狀態</p>
                <h2 id="player-status" class="text-xs text-emerald-400 font-bold mt-2">-</h2>
            </div>
        </div>

        <div class="bg-slate-800/80 p-5 rounded-2xl border border-slate-700 shadow-xl mb-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-sm font-bold text-indigo-400 border-b border-slate-700 pb-2">殭屍能力實值詳情</h3>
                <h2 id="last-action" class="text-xs text-amber-400 font-bold">-</h2>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-slate-900/50 p-3 rounded-lg border border-slate-700 text-center">
                    <p class="text-[10px] text-slate-500">血量 (HP)</p>
                    <h4 id="real-hp" class="text-xl font-mono text-red-400">--</h4>
                </div>
                <div class="bg-slate-900/50 p-3 rounded-lg border border-slate-700 text-center">
                    <p class="text-[10px] text-slate-500">攻擊 (ATK)</p>
                    <h4 id="real-atk" class="text-xl font-mono text-amber-400">--</h4>
                </div>
                <div class="bg-slate-900/50 p-3 rounded-lg border border-slate-700 text-center">
                    <p class="text-[10px] text-slate-500">偵測 (DET)</p>
                    <h4 id="real-det" class="text-xl font-mono text-purple-400">--</h4>
                </div>
                <div class="bg-slate-900/50 p-3 rounded-lg border border-slate-700 text-center">
                    <p class="text-[10px] text-slate-500">速度 (SPD)</p>
                    <h4 id="real-spd" class="text-xl font-mono text-emerald-400">--</h4>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-2xl">
                <h3 class="text-sm font-bold text-slate-300 mb-4">玩家性能趨勢 (K/D)</h3>
                <div class="chart-container"><canvas id="kdChart"></canvas></div>
            </div>
            <div class="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-2xl">
                <h3 class="text-sm font-bold text-slate-300 mb-4">殭屍屬性演化 (四項指標)</h3>
                <div class="chart-container"><canvas id="paramChart"></canvas></div>
            </div>
        </div>
    </div>

    <script>
        let selectedPlayer = 'latest';
        let currentHistory = [];
        const BASE = {{ BASE_STATS | tojson }};

        const kdCtx = document.getElementById('kdChart').getContext('2d');
        const paramCtx = document.getElementById('paramChart').getContext('2d');

        const kdChart = new Chart(kdCtx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'K/D', borderColor: '#22d3ee', data: [], tension: 0.4, fill: true, pointRadius: 2 }] },
            options: { responsive: true, maintainAspectRatio: false }
        });

        const paramChart = new Chart(paramCtx, {
            type: 'line',
            data: { 
                labels: [], 
                datasets: [
                    { label: 'HP', borderColor: '#f87171', data: [], tension: 0.2, borderWidth: 3 },
                    { label: 'ATK', borderColor: '#fbbf24', data: [], tension: 0.2, borderWidth: 2, borderDash: [5, 5] },
                    { label: 'DET', borderColor: '#a78bfa', data: [], tension: 0.2, borderWidth: 2 },
                    { label: 'SPD', borderColor: '#34d399', data: [], tension: 0.2, borderWidth: 3, borderDash: [2, 2] }
                ] 
            },
            options: { 
                responsive: true, maintainAspectRatio: false, 
                scales: { y: { min: 0.6, max: 1.6 } }
            }
        });

        async function updateDashboard() {
            try {
                const res = await fetch('/get_history');
                const allData = await res.json();
                const players = Object.keys(allData);
                const select = document.getElementById('playerSelect');
                if(players.length !== (select.options.length - 1)) {
                    select.innerHTML = '<option value="latest">--- 自動追蹤最新 ---</option>';
                    players.forEach(p => { select.innerHTML += `<option value="${p}">${p}</option>`; });
                    select.value = selectedPlayer;
                }

                if(players.length > 0) {
                    const targetID = (selectedPlayer === 'latest') ? players[players.length - 1] : selectedPlayer;
                    document.getElementById('current-player').innerText = targetID;
                    const session = allData[targetID];
                    currentHistory = session.history;

                    if(currentHistory.length > 0) {
                        const last = currentHistory[currentHistory.length - 1];
                        document.getElementById('last-action').innerText = last.action;
                        document.getElementById('player-status').innerText = last.status;
                        document.getElementById('kd-display').innerText = last.kd;
                        document.getElementById('recovery-steps').innerText = session.recovery_counter || 0;

                        document.getElementById('real-hp').innerText = (last.hp * BASE.HP).toFixed(1);
                        document.getElementById('real-atk').innerText = (last.atk * BASE.ATK).toFixed(1);
                        document.getElementById('real-det').innerText = (last.det * BASE.DET).toFixed(1);
                        document.getElementById('real-spd').innerText = (last.spd * BASE.SPD).toFixed(2);

                        const labels = currentHistory.map((_, i) => i);
                        kdChart.data.labels = labels;
                        kdChart.data.datasets[0].data = currentHistory.map(h => h.kd);
                        kdChart.update('none');

                        paramChart.data.labels = labels;
                        paramChart.data.datasets[0].data = currentHistory.map(h => h.hp);
                        paramChart.data.datasets[1].data = currentHistory.map(h => h.atk);
                        paramChart.data.datasets[2].data = currentHistory.map(h => h.det);
                        paramChart.data.datasets[3].data = currentHistory.map(h => h.spd);
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


# --- 5. 核心邏輯修正 (⚠️ 修正降幅與回升) ---

@app.route('/')
def dashboard_home():
    return render_template_string(DASHBOARD_HTML, BASE_STATS=BASE_STATS)


@app.route('/get_history')
def get_history_api():
    return jsonify(PLAYER_SESSIONS)


@app.route("/adjust_difficulty", methods=["POST"])
def adjust_difficulty():
    global PLAYER_SESSIONS
    data = request.get_json()
    player_id = data.get("player_id", "Subject")
    status = data.get("status", "Alive")
    scene = data.get("scene_name", "Unknown")
    game_time = data.get("game_time", 0)

    if player_id not in PLAYER_SESSIONS:
        PLAYER_SESSIONS[player_id] = {
            "params": {"HP_Mult": 1.0, "ATK_Mult": 1.0, "Det_Range": 1.0, "Move_Speed": 1.0},
            "history": [], "has_calibrated": False,
            "recovery_counter": 0  # 新增：恢復期計數器
        }

    session = PLAYER_SESSIONS[player_id]
    is_tut = (scene == "Tutorial")

    # 死亡處理：大幅跳水
    if status == "Dead":
        # ⚠️ 強力降難：一次跳回 70% 的差距
        new_params, action = adjust_difficulty_dda(
            session["params"], {"kill_count": 0, "death_count": 10},
            P_Strong, P_Weak, is_tutorial=False, is_first_game=True
        )
        # 手動加強降幅 (針對死亡事件做額外處理)
        for key in session["params"]:
            session["params"][key] = session["params"][key] + (P_Weak[key] - session["params"][key]) * 0.7

        action = "Emergency Down (Death)"
        session["recovery_counter"] = 4  # 設定 4 個週期的保護期
    else:
        # 正常 DDA 判定
        if session["recovery_counter"] > 0:
            # ⚠️ 恢復期中：即便 K/D 很高，也限制加難的速度
            new_params, action = adjust_difficulty_dda(session["params"], data, P_Strong, P_Weak, is_tut, False)

            # 如果 AI 想要加難，限制其增幅
            if "Up" in action:
                for key in session["params"]:
                    # 只允許原本增幅的 30%
                    diff = new_params[key] - session["params"][key]
                    session["params"][key] += diff * 0.3
                action += " (Restricted Recovery)"
            else:
                session["params"] = new_params

            session["recovery_counter"] -= 1
        else:
            # 全速運作
            is_first = (not session["has_calibrated"] and game_time > 2 and not is_tut)
            if is_first: session["has_calibrated"] = True

            new_params, action = adjust_difficulty_dda(session["params"], data, P_Strong, P_Weak, is_tut, is_first)
            session["params"] = new_params

    # 記錄日誌
    kill_count = data.get('kill_count', 0)
    death_count = data.get('death_count', 0)
    kd_ratio = kill_count / (death_count if death_count > 0 else 0.5)

    session["history"].append({
        "kd": round(kd_ratio, 2),
        "hp": round(session["params"]["HP_Mult"], 2),
        "atk": round(session["params"]["ATK_Mult"], 2),
        "det": round(session["params"]["Det_Range"], 2),
        "spd": round(session["params"]["Move_Speed"], 2),
        "action": action, "status": status
    })

    init_csv_header()
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%H:%M:%S"), player_id, data.get("mode"), scene, status,
            f"{kd_ratio:.2f}",
            f"{session['params']['HP_Mult']:.2f}", f"{session['params']['ATK_Mult']:.2f}",
            f"{session['params']['Det_Range']:.2f}", f"{session['params']['Move_Speed']:.2f}",
            f"{session['params']['HP_Mult'] * BASE_STATS['HP']:.1f}",
            f"{session['params']['ATK_Mult'] * BASE_STATS['ATK']:.1f}",
            f"{session['params']['Det_Range'] * BASE_STATS['DET']:.1f}",
            f"{session['params']['Move_Speed'] * BASE_STATS['SPD']:.2f}",
            action
        ])

    return jsonify({"adjusted_params": session["params"], "adjustment_action": action})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
import requests
import time
import json


def simulate_unity_send(label, scene, kills, deaths, dmg_dealt, dmg_taken, play_time):
    url = "http://127.0.0.1:5050/adjust_difficulty"
    payload = {
        "scene_name": scene,
        "kill_count": kills,
        "death_count": deaths,
        "damage_dealt": dmg_dealt,
        "damage_taken": dmg_taken,
        "game_time": play_time
    }

    print(f"\n>>> 模擬情境：{label}")
    try:
        response = requests.post(url, json=payload)
        result = response.json()
        print(f"後端動作：{result.get('adjustment_action')}")
        print(f"評估分數：{result.get('evaluation_score'):.2f}")
    except Exception as e:
        print(f"連線失敗，請確認 flask_api.py 是否已啟動：{e}")


# --- 開始模擬流程 ---

# 1. 模擬教學關卡 (DDA 應該鎖定不調整) [cite: 250, 251]
simulate_unity_send("教學關卡 - 穩定遊玩", "Tutorial", 2, 0, 300, 10, 60)

# 2. 模擬進入實戰的第一波：玩家表現極強 (應該觸發 0.5 的快速校準) [cite: 302, 305]
simulate_unity_send("實戰開始 - 玩家是大神", "MainGame", 15, 0, 1200, 5, 120)

# 3. 模擬實戰第二波：玩家表現稍弱 (應該觸發 0.2 的微調)
simulate_unity_send("實戰持續 - 玩家突然失誤", "MainGame", 1, 5, 200, 400, 180)

print("\n>>> 模擬結束")
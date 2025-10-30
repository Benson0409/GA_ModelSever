import requests

# Unity 模擬傳送的玩家數據
player_data = {
    "kill_count": 30,
    "death_count": 20,
    "damage_taken": 500.0,
    "damage_dealt": 80.0,
    "game_time": 280
}

# 傳送到 Flask API
response = requests.post("http://127.0.0.1:5050/adjust_difficulty", json=player_data)

# 顯示回傳內容（JSON 格式）
print("✅ 回傳 JSON：")
print(response.json())
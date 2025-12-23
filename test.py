import requests
import time
import math
import random

# API 位置
URL = "http://127.0.0.1:5050/adjust_difficulty"

# 同步基準線 (與 Unity / API 保持一致)
BASE = {"HP": 100.0, "ATK": 10.0, "DET": 20.0, "SPD": 2.5}


def send_sim(p_id, mode, scene, status, kills, deaths, dmg_in, dmg_out, step):
    payload = {
        "player_id": p_id,
        "mode": mode,
        "scene_name": scene,
        "status": status,
        "kill_count": kills,
        "death_count": deaths,
        "damage_taken": dmg_in,
        "damage_dealt": dmg_out,
        "game_time": step * 5
    }
    try:
        response = requests.post(URL, json=payload, timeout=5)
        if response.status_code == 200:
            res = response.json()
            p = res['adjusted_params']

            # 計算當前傳送的 K/D (避免除以 0)
            kd = kills / (deaths if deaths > 0 else 0.5)

            print(f"[{p_id}] Step:{step:2} | K/D:{kd:4.1f} | 狀態:{status:5s} | 動作: {res['adjustment_action']:18s}")
            print(
                f"    -> 實值回饋: HP:{p['HP_Mult'] * BASE['HP']:5.1f}, ATK:{p['ATK_Mult'] * BASE['ATK']:4.1f}, DET:{p['Det_Range'] * BASE['DET']:4.1f}, SPD:{p['Move_Speed'] * BASE['SPD']:4.2f}")
        else:
            print(f"❌ 伺服器錯誤: {response.status_code}")
    except Exception as e:
        print(f"❌ 連連失敗: {e}")


def run_realistic_test():
    print("=" * 110)
    print("🚀 啟動強化版 DDA 邏輯驗證測試 (模擬路徑：強勢 -> 崩潰 -> 復甦)")
    print("   目標：觀察 K/D 劇烈波動下，模型是否能精準執行 [Adjusted Up] 與 [Emergency Down]")
    print("=" * 110)

    # 模擬受試者：一名表現有明顯波動的玩家
    # 這裡我們模擬兩個受試者，一個接一個出現，以測試 Dashboard 的自動追蹤功能
    subjects = ["Adaptive_Subject_01", "Adaptive_Subject_02"]

    for p_id in subjects:
        print(f"\n🌟 --- 開始測試受試者：{p_id} --- 🌟")

        # 每個玩家模擬 40 個步驟 (約 3.3 分鐘數據)
        for step in range(1, 41):
            status = "Alive"

            # --- 模擬玩家表現階段：波浪起伏 ---
            if step <= 10:
                # 第一階段：強勢 (K/D > 0.7)
                kills = 8 + random.randint(-2, 2)
                deaths = 0
                stage = "強勢期"

            elif 11 <= step <= 25:
                # 第二階段：表現大幅下滑 (K/D 跌破 0.3)
                kills = 0 if step % 3 != 0 else 1
                deaths = 1 if step % 5 == 0 else 0
                stage = "下滑期"

                # 模擬玩家在第 20 步不幸死亡
                if step == 20:
                    status = "Dead"
                    stage = "玩家死亡"

            else:
                # 第三階段：重新復甦 (K/D 再次升高)
                kills = 4 + (step - 25) // 2
                deaths = 0
                stage = "復甦期"

            send_sim(p_id, "1", "MainGame", status, kills, deaths, step * 2, kills * 30, step)

            # 加速模擬執行 (0.1s 代表 5s)
            time.sleep(0.1)

    print("\n" + "=" * 110)
    print("✅ 模擬實驗完成！")
    print("請開啟儀表板 (http://127.0.0.1:5050) 查看自動追蹤與 CSV 紀錄。")
    print("=" * 110)


if __name__ == "__main__":
    run_realistic_test()
import requests
import time
import random

# API 位置
URL_DDA = "http://127.0.0.1:5050/adjust_difficulty"
URL_FINAL = "http://127.0.0.1:5050/submit_final_result"


def send_step(p_id, kills, deaths, status, step):
    payload = {
        "player_id": p_id,
        "mode": "1",  # 測試 5秒組
        "scene_name": "MainGame",
        "status": status,
        "kill_count": kills,
        "death_count": deaths,
        "game_time": step * 5
    }
    try:
        res = requests.post(URL_DDA, json=payload, timeout=5).json()
        p = res['adjusted_params']
        print(
            f"[{p_id}] 步數:{step:2} | K/D:{(kills / (deaths if deaths > 0 else 0.5)):4.1f} | 狀態:{status:5s} | 動作:{res['adjustment_action']}")
        print(f"    -> 當前倍率: HP:{p['HP_Mult']:.2f}, SPD:{p['Move_Speed']:.2f}")
    except Exception as e:
        print(f"❌ 傳送失敗: {e}")


def run_simulation():
    p_id = "Sim_Varied_User_" + str(random.randint(10, 99))
    print(f"==================================================")
    print(f"🚀 開始模擬受試者變化的遊玩過程: {p_id}")
    print(f"==================================================")

    # 階段 1：強勢期 (Step 1-10) -> 難度應該上升
    print("\n--- 階段 1: 玩家表現強勢 (預期：難度上升) ---")
    for i in range(1, 11):
        send_step(p_id, kills=12, deaths=0, status="Alive", step=i)
        time.sleep(0.5)

    # 階段 2：平衡期 (Step 11-15) -> K/D 介於 0.3 ~ 0.7，難度應該持平
    print("\n--- 階段 2: 表現平衡 (預期：Stay Balanced) ---")
    for i in range(11, 16):
        # K/D = 1 / 2 = 0.5 (落在 0.3~0.7 區間)
        send_step(p_id, kills=1, deaths=2, status="Alive", step=i)
        time.sleep(0.5)

    # 階段 3：弱勢期 (Step 16-20) -> 難度應該下降
    print("\n--- 階段 3: 表現下滑 (預期：難度下降) ---")
    for i in range(16, 21):
        # K/D = 0 / 2 = 0
        send_step(p_id, kills=0, deaths=2, status="Alive", step=i)
        time.sleep(0.5)

    # 階段 4：死亡突發 (Step 21) -> 難度應該大幅急降
    print("\n--- 階段 4: 玩家死亡 (預期：Emergency Down) ---")
    send_step(p_id, kills=0, deaths=1, status="Dead", step=21)

    print("\n--- 階段 5: 死亡後的冷靜期 (預期：Restricted Recovery) ---")
    for i in range(22, 26):
        # 即使表現變好，回升速度也應該被限制
        send_step(p_id, kills=10, deaths=0, status="Alive", step=i)
        time.sleep(0.5)

    # 最後傳送通關數據
    final_payload = {
        "player_id": p_id,
        "mode": "1",
        "totalDamage": 5000,
        "damageTaken": 800,
        "kills": 150,
        "deaths": 5,
        "completionTime": 130.0,
        "result": "Completed"
    }
    requests.post(URL_FINAL, json=final_payload)
    print(f"\n✅ 模擬結束，請檢查 Dashboard 上的曲線變化。")


if __name__ == "__main__":
    run_simulation()
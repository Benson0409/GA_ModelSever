import random
import numpy as np
from deap import base, creator, tools



# --- 評估函式 ---
def simulate_game_run(hp_mult, atk_mult, det_range, move_speed_mult):
    base_kill = 10
    base_death = 3
    base_dealt = 1000
    base_taken = 70
    base_time = 300

    # 擊殺數（越高代表太強，數值應降低）
    kill_count = base_kill / (
        (0.8 * hp_mult) +
        (0.1 * atk_mult) +
        (0.1 * move_speed_mult)
    )

    # 死亡數（越高代表太弱，數值應上升）
    death_count = base_death * (
        (0.5 * atk_mult) +
        (0.2 * det_range) +
        (0.3 * hp_mult)
    )

    # 傷害輸出（若高但擊殺少 → 沒有效率）
    damage_dealt = base_dealt / (
        (0.8 * hp_mult) +
        (0.2 * atk_mult)
    )

    # 承受傷害（太高代表承受過多，屬於弱者行為）
    damage_taken = base_taken * (
        (0.6 * atk_mult) +
        (0.4 * move_speed_mult)
    ) / hp_mult

    # 遊戲時間（比重降低，只代表熟練程度或風格）
    game_time = base_time * (
        (0.3 * hp_mult) + (0.1 * atk_mult)
    )

    return {
        'kill_count': max(0, round(kill_count)),
        'death_count': max(0, round(death_count)),
        'damage_taken': max(0.0, damage_taken),
        'damage_dealt': max(0.0, damage_dealt),
        'game_time': max(1, round(game_time))
    }

def evaluate_from_unity(individual, player_data):
    hp_mult, atk_mult, det_range, move_speed_mult = individual

    kill = player_data.get('kill_count', 0)
    death = player_data.get('death_count', 1)
    damage_taken = player_data.get('damage_taken', 0.0)
    damage_dealt = player_data.get('damage_dealt', 0.0)
    game_time = player_data.get('game_time', 1)

    # --- 主要權重設計 ---
    ALPHA = 10.0     # 擊殺數（越高越好 → 難度上升）
    BETA = -15.0     # 死亡數（越高越壞 → 難度下降）
    GAMMA = -0.8     # 承受傷害（越高越壞 → 難度下降）
    DELTA = 0.005    # 造成傷害（越高代表表現佳，但需與死亡搭配）
    EPSILON = -0.01  # 遊戲時間（越長略降難度）
    ZETA = 0.5       # 參數懲罰：避免極端數值

    # --- 新增互動條件 ---
    # 若高傷害＋高死亡 → 懲罰（代表打太激進）
    if damage_dealt > 1000 and death > 3:
        DELTA = -0.005  # 將造成傷害變為懲罰
        GAMMA = -1.0    # 承受傷害懲罰加重

    # 若高傷害＋高擊殺＋低死亡 → 顯著提高難度
    elif damage_dealt > 1000 and kill > 10 and death <= 2:
        ALPHA = 12.0
        DELTA = 0.01    # 額外獎勵火力輸出

    # 若擊殺低、死亡低但傷害高 → 表示敵人太硬
    elif kill < 5 and death <= 1 and damage_dealt > 800:
        ALPHA = 8.0
        DELTA = 0.02    # 鼓勵調高難度

    raw_fitness = (ALPHA * kill) + (BETA * death) + (GAMMA * damage_taken) + \
                  (DELTA * damage_dealt) + (EPSILON * game_time)

    parameter_cost = hp_mult + atk_mult + det_range + move_speed_mult
    fitness_value = raw_fitness - (ZETA * parameter_cost)

    return fitness_value

# --- DDA 調整邏輯 ---
ADJUSTMENT_RATE = 0.2 #調整幅度
STRONG_THRESHOLD = 5.0
WEAK_THRESHOLD = 2.0

ADJUSTMENT_RATE = 0.2
STRONG_THRESHOLD = 8.0   # 擊殺 / 死亡 比高於 8 → 強
WEAK_THRESHOLD = 2.0     # 擊殺 / 死亡 比低於 2 → 弱

def adjust_difficulty_dda(current_params, player_results, P_Strong, P_Weak):
    kill = player_results.get('kill_count', 0)
    death = player_results.get('death_count', 1)

    if death == 0:
        performance_ratio = kill * 2.0  # 沒死過 → 強勢
    else:
        performance_ratio = kill / death

    new_params = current_params.copy()
    action = "No Change"

    if performance_ratio > STRONG_THRESHOLD:
        print("🧩 玩家表現太強，難度上調")
        target_params = P_Strong
        action = "Adjusted Up"

    elif performance_ratio < WEAK_THRESHOLD:
        print("🧩 玩家表現太弱，難度下調")
        target_params = P_Weak
        action = "Adjusted Down"

    else:
        print("🧩 玩家表現適中，維持現狀")
        return current_params, action

    # --- 微調向目標靠近 ---
    for key in current_params:
        current_val = current_params[key]
        target_val = target_params[key]
        step = (target_val - current_val) * ADJUSTMENT_RATE
        new_params[key] = current_val + step

        # 邊界修正
        if step > 0:
            new_params[key] = min(new_params[key], target_val)
        else:
            new_params[key] = max(new_params[key], target_val)

    return new_params, action
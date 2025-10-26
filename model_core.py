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

    # --- 1. 擊殺數（越高越好，會被懲罰）
    kill_count = base_kill / (
            (0.6 * hp_mult) +
            (0.25 * atk_mult) +
            (0.1 * move_speed_mult) +
            (0.05 * det_range)
    )

    # --- 2. 玩家死亡數（越高越好，會被獎勵）
    death_count = base_death * (
            (0.6 * atk_mult) +
            (0.2 * det_range) +
            (0.3 * move_speed_mult) +
            (0.4 * hp_mult)
    )

    # --- 3. 玩家造成的傷害（越高越壞，會被懲罰）
    damage_dealt = base_dealt / (
            (0.7 * hp_mult) +
            (0.1 * move_speed_mult)
    )

    # --- 4. 玩家承受傷害（越高越好，會被獎勵）
    damage_taken = base_taken * (
            (0.7 * atk_mult) +
            (0.3 * move_speed_mult)
    ) / hp_mult

    # --- 5. 遊戲時間（越短越好，會被懲罰）
    game_time = base_time * (
            (0.8 * hp_mult) + (0.2 * atk_mult)
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

    ALPHA = -5.0
    BETA = 10.0
    GAMMA = 0.5
    DELTA = -0.1
    EPSILON = -0.1
    ZETA = 0.5

    raw_fitness = (ALPHA * kill) + (BETA * death) + (GAMMA * damage_taken) + \
                  (DELTA * damage_dealt) + (EPSILON * game_time)

    parameter_cost = hp_mult + atk_mult + det_range + move_speed_mult

    fitness_value = raw_fitness - (ZETA * parameter_cost)
    return fitness_value

# --- DDA 調整邏輯 ---
ADJUSTMENT_RATE = 0.2
STRONG_THRESHOLD = 5.0
WEAK_THRESHOLD = 2.0

def adjust_difficulty_dda(current_params, player_results, P_Strong, P_Weak):
    kill = player_results.get('kill_count', 0)
    death = player_results.get('death_count', 1)

    performance_ratio = kill / death
    new_params = current_params.copy()
    action = "No Change"  # 預設 action 為 No Change

    # 判斷調整方向
    if performance_ratio > STRONG_THRESHOLD:
        print("DDA 判斷: 玩家表現太強，難度上調。")

        target_params = P_Strong
        action = "Adjusted Up"

    elif performance_ratio < WEAK_THRESHOLD:
        print("DDA 判斷: 玩家表現太弱，難度下調。")

        target_params = P_Weak
        action = "Adjusted Down"  # 設定調整動作

    else:
        # --- 修正後的邏輯：直接返回當前參數和 No Change action ---
        print("DDA 判斷: 難度適中，保持不變。")
        return current_params, action  # <-- 確保回傳 (參數, Action) 兩個值

    # --- 執行參數微調 (只在 Adjusted Up/Down 時執行) ---
    for key in current_params:
        current_val = current_params[key]
        target_val = target_params[key]

        step = (target_val - current_val) * ADJUSTMENT_RATE
        new_params[key] = current_val + step

        # 額外邏輯：確保微調後的參數不會跑出 GA 的邊界
        if step > 0:
            new_params[key] = min(new_params[key], target_val)
        else:
            new_params[key] = max(new_params[key], target_val)

    # 調整完成後，返回新參數和 action
    return new_params, action
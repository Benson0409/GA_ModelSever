import random
import numpy as np


# --- 1. 模擬函式 (修正 HP 邏輯) ---
def simulate_game_run(hp_mult, atk_mult, det_range, move_speed_mult):
    base_kill, base_death = 25, 3
    base_dealt, base_taken, base_time = 2700, 200, 450

    # 擊殺數：HP 越高，擊殺越難 (HP 在分母正確)
    kill_count = base_kill / ((0.8 * hp_mult) + (0.1 * atk_mult) + (0.1 * move_speed_mult))
    # 死亡數：HP 越高，玩家越容易死 (正確)
    death_count = base_death * ((0.5 * atk_mult) + (0.2 * det_range) + (0.3 * hp_mult))
    # 傷害輸出：HP 越高，玩家需要打更多血量 (正確)
    damage_dealt = base_dealt / ((0.7 * hp_mult) + (0.2 * atk_mult))

    # --- 關鍵修正處：承受傷害 ---
    # 改為 * hp_mult：殭屍血越厚，存活時間越長，玩家受傷越多
    damage_taken = base_taken * ((0.6 * atk_mult) + (0.4 * move_speed_mult)) * hp_mult

    game_time = base_time * ((0.5 * hp_mult) + (0.3 * atk_mult))

    return {
        'kill_count': max(0, round(kill_count)),
        'death_count': max(0, round(death_count)),
        'damage_taken': max(0.0, damage_taken),
        'damage_dealt': max(0.0, damage_dealt),
        'game_time': max(1, round(game_time))
    }


# --- 2. 評估函式 (保持不變) ---
def evaluate_from_unity(individual, player_data):
    hp_mult, atk_mult, det_range, move_speed_mult = individual
    kill = player_data.get('kill_count', 0)
    death = player_data.get('death_count', 1)
    damage_taken = player_data.get('damage_taken', 0.0)
    damage_dealt = player_data.get('damage_dealt', 0.0)
    game_time = player_data.get('game_time', 1)

    ALPHA, BETA, GAMMA, DELTA, EPSILON, ZETA = 10.0, -15.0, -0.8, 0.005, -0.01, 0.5

    if damage_dealt > 1000 and death > 3:
        DELTA, GAMMA = -0.005, -1.0
    elif damage_dealt > 1000 and kill > 10 and death <= 2:
        ALPHA, DELTA = 12.0, 0.01
    elif kill < 5 and death <= 1 and damage_dealt > 800:
        ALPHA, DELTA = 8.0, 0.15

    raw_fitness = (ALPHA * kill) + (BETA * death) + (GAMMA * damage_taken) + \
                  (DELTA * damage_dealt) + (EPSILON * game_time)
    parameter_cost = hp_mult + atk_mult + det_range + move_speed_mult
    return raw_fitness - (ZETA * parameter_cost)


# --- 3. DDA 調整邏輯 (優化印出格式) ---
ADJUSTMENT_RATE_NORMAL = 0.2
ADJUSTMENT_RATE_FAST = 0.3
STRONG_THRESHOLD = 7.0
WEAK_THRESHOLD = 3.0


def adjust_difficulty_dda(current_params, player_results, P_Strong, P_Weak, is_tutorial=False, is_first_game=False):
    if is_tutorial:
        print(">>>> [系統監測] 教學關卡中，數值鎖定。")
        return current_params, "Tutorial Monitoring"

    kill = player_results.get('kill_count', 0)
    death = player_results.get('death_count', 1)
    ratio = kill / (death if death > 0 else 0.5)

    rate = ADJUSTMENT_RATE_FAST if is_first_game else ADJUSTMENT_RATE_NORMAL
    new_params = current_params.copy()

    if ratio > STRONG_THRESHOLD:
        print(f"\n🔥 玩家太強 (K/D: {ratio:.1f})，進行難度上調：")
        target_params, action = P_Strong, "Adjusted Up"
    elif ratio < WEAK_THRESHOLD:
        print(f"\n💧 玩家太弱 (K/D: {ratio:.1f})，進行難度下調：")
        target_params, action = P_Weak, "Adjusted Down"
    else:
        return current_params, "Stay Balanced"

    param_map = {"HP_Mult": "血量", "ATK_Mult": "攻擊力", "Det_Range": "偵測距離", "Move_Speed": "移動速度"}
    for key in current_params:
        old_val = current_params[key]
        target_val = target_params[key]
        new_params[key] = old_val + (target_val - old_val) * rate
        print(f"  - {param_map[key]}：{old_val:.2f} 倍 調整至 {new_params[key]:.2f} 倍")
    print("------------------------------------------\n")

    return new_params, action
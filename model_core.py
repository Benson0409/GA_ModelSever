import random
import numpy as np


# --- 1. 模擬函式 (維持不變，用於訓練) ---
def simulate_game_run(hp_mult, atk_mult, det_range, move_speed_mult):
    base_kill, base_death = 25, 3
    base_dealt, base_taken, base_time = 2700, 200, 450
    kill_count = base_kill / ((0.8 * hp_mult) + (0.1 * atk_mult) + (0.1 * move_speed_mult))
    death_count = base_death * ((0.5 * atk_mult) + (0.2 * det_range) + (0.3 * hp_mult))
    damage_dealt = base_dealt / ((0.7 * hp_mult) + (0.2 * atk_mult))
    damage_taken = base_taken * ((0.6 * atk_mult) + (0.4 * move_speed_mult)) * hp_mult
    game_time = base_time * ((0.5 * hp_mult) + (0.3 * atk_mult))
    return {
        'kill_count': max(0, round(kill_count)), 'death_count': max(0, round(death_count)),
        'damage_taken': max(0.0, damage_taken), 'damage_dealt': max(0.0, damage_dealt),
        'game_time': max(1, round(game_time))
    }


# --- 2. 評估函式 ---
def evaluate_from_unity(individual, player_data):
    hp_mult, atk_mult, det_range, move_speed_mult = individual
    kill = player_data.get('kill_count', 0)
    death = player_data.get('death_count', 1)
    damage_taken = player_data.get('damage_taken', 0.0)
    damage_dealt = player_data.get('damage_dealt', 0.0)
    game_time = player_data.get('game_time', 1)

    ALPHA, BETA, GAMMA, DELTA, EPSILON, ZETA = 10.0, -15.0, -0.8, 0.005, -0.01, 0.5
    raw_fitness = (ALPHA * kill) + (BETA * death) + (GAMMA * damage_taken) + (DELTA * damage_dealt) + (
                EPSILON * game_time)
    parameter_cost = hp_mult + atk_mult + det_range + move_speed_mult
    return raw_fitness - (ZETA * parameter_cost)


# --- 3. DDA 調整引擎 (平滑化修正) ---
ADJUSTMENT_RATE_NORMAL = 0.15  # 從 0.2 降到 0.15，讓變化更細膩
ADJUSTMENT_RATE_FAST = 0.25  # 從 0.35 降到 0.25，避免開場難度暴跌/暴漲
STRONG_THRESHOLD = 8.0  # 稍微提高強勢門檻
WEAK_THRESHOLD = 2.0  # 稍微降低弱勢門檻


def adjust_difficulty_dda(current_params, player_results, P_Strong, P_Weak, is_tutorial=False, is_first_game=False):
    if is_tutorial:
        return current_params, "Tutorial Monitoring"

    kill = player_results.get('kill_count', 0)
    death = player_results.get('death_count', 1)
    ratio = kill / (death if death > 0 else 0.5)

    rate = ADJUSTMENT_RATE_FAST if is_first_game else ADJUSTMENT_RATE_NORMAL
    new_params = current_params.copy()

    if ratio > STRONG_THRESHOLD:
        target_params, action = P_Strong, "Adjusted Up"
    elif ratio < WEAK_THRESHOLD:
        target_params, action = P_Weak, "Adjusted Down"
    else:
        return current_params, "Stay Balanced"

    for key in current_params:
        old_val = current_params[key]
        target_val = target_params[key]
        # 漸進式調整
        new_params[key] = old_val + (target_val - old_val) * rate

    return new_params, action
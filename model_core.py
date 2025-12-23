import random
import numpy as np


# --- 1. 模擬函式 (GA 訓練與驗證使用) ---
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


# --- 2. 評估函式 (DDA 效果評分) ---
def evaluate_from_unity(individual, player_data):
    hp_mult, atk_mult, det_range, move_speed_mult = individual
    kill = player_data.get('kill_count', 0)
    death = player_data.get('death_count', 1)
    damage_taken = player_data.get('damage_taken', 0.0)
    damage_dealt = player_data.get('damage_dealt', 0.0)
    game_time = player_data.get('game_time', 1)

    # 權重係數：ALPHA(擊殺), BETA(死亡), GAMMA(受傷), DELTA(輸出), EPSILON(時長), ZETA(難度成本)
    ALPHA, BETA, GAMMA, DELTA, EPSILON, ZETA = 10.0, -15.0, -0.8, 0.005, -0.01, 0.5
    raw_fitness = (ALPHA * kill) + (BETA * death) + (GAMMA * damage_taken) + (DELTA * damage_dealt) + (
                EPSILON * game_time)
    parameter_cost = hp_mult + atk_mult + det_range + move_speed_mult
    return raw_fitness - (ZETA * parameter_cost)


# --- 3. DDA 調整引擎 (核心邏輯) ---
# 正常調整速率 (12%)
ADJUSTMENT_RATE_NORMAL = 0.12
# 校準期/開場調整速率 (5%)
ADJUSTMENT_RATE_FAST = 0.05
# 加難門檻 (K/D > 0.7 觸發)
STRONG_THRESHOLD = 0.7
# 降難門檻 (K/D < 0.3 觸發)
WEAK_THRESHOLD = 0.3


def adjust_difficulty_dda(current_params, player_results, P_Strong, P_Weak, is_tutorial=False, is_first_game=False):
    """
    根據玩家表現動態計算下一階段的殭屍屬性倍率
    """
    # 教學關卡僅監測，回傳原參數
    if is_tutorial:
        return current_params, "Tutorial Monitoring"

    kill = player_results.get('kill_count', 0)
    death = player_results.get('death_count', 0)
    # 計算 K/D，避免除以 0
    ratio = kill / (death if death > 0 else 0.5)

    # 決定當前步長的調整速率
    rate = ADJUSTMENT_RATE_FAST if is_first_game else ADJUSTMENT_RATE_NORMAL
    new_params = current_params.copy()

    # 難度判定邏輯
    if ratio > STRONG_THRESHOLD:
        target_params, action = P_Strong, "Adjusted Up"
    elif ratio < WEAK_THRESHOLD:
        target_params, action = P_Weak, "Adjusted Down"
    else:
        # 處於平衡區間，維持現狀
        return current_params, "Stay Balanced"

    # 使用線性插值 (Lerp) 進行參數更新
    for key in current_params:
        old_val = current_params[key]
        target_val = target_params[key]
        # 公式：現在值 + (目標值 - 現在值) * 速率
        new_params[key] = old_val + (target_val - old_val) * rate

    return new_params, action
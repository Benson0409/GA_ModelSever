from deap import base, creator, tools, algorithms
import random
import numpy as np
import pickle
from model_core import (
    simulate_game_run,
    evaluate_from_unity,
)

# --- 基因範圍設定 ---
# 血量
HP_BOUNDS = [0.5, 3.0]
# 攻擊力
ATK_BOUNDS = [0.5, 3.0]
# 搜尋範圍
DET_BOUNDS = [0.5, 2.5]
# 移動速度
SPEED_BOUNDS = [0.5, 2.0]

# 設定 GA 參數
POP_SIZE = 30
N_GEN = 40
CX_PB = 0.7
MUT_PB = 0.2

# 建立適應度與個體類型
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)

toolbox = base.Toolbox()
# --- 基因與個體生成 (使用前面定義的範圍) ---
toolbox.register("attr_hp_mult", random.uniform, *HP_BOUNDS)
toolbox.register("attr_atk_mult", random.uniform, *ATK_BOUNDS)
toolbox.register("attr_det_range", random.uniform, *DET_BOUNDS)
toolbox.register("attr_move_speed", random.uniform, *SPEED_BOUNDS)


toolbox.register("individual", tools.initCycle, creator.Individual,
                 (toolbox.attr_hp_mult, toolbox.attr_atk_mult, toolbox.attr_det_range, toolbox.attr_move_speed),
                 n=1)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

def checkBounds(min_val, max_val):
    """
    返回一個裝飾器，用於將交配和突變操作的結果裁剪到參數的有效範圍內。
    """
    # 這裡的 min_val 和 max_val 實際上沒有使用，但保留以符合原結構。
    # 實際的裁剪邊界將直接使用外部定義的全局 BOUNDS 變數。

    def decorator(func):
        def wrapper(*args, **kwargs):
            offspring = func(*args, **kwargs)

            # 遍歷新產生的所有個體 (染色體)
            for individual in offspring:

                # --- 引用最新的全局 BOUNDS 變數進行裁剪 ---

                # 裁剪 P1: HP_Mult [0.5, 3.0]
                individual[0] = np.clip(individual[0], HP_BOUNDS[0], HP_BOUNDS[1])

                # 裁剪 P2: ATK_Mult [0.5, 3.0]
                individual[1] = np.clip(individual[1], ATK_BOUNDS[0], ATK_BOUNDS[1])

                # 裁剪 P3: Det_Range [0.5, 2.5]
                individual[2] = np.clip(individual[2], DET_BOUNDS[0], DET_BOUNDS[1])

                # 裁剪 P4: Move_Speed [0.5, 2.0]
                individual[3] = np.clip(individual[3], SPEED_BOUNDS[0], SPEED_BOUNDS[1])

            return offspring
        return wrapper
    return decorator

# 訓練強殭屍：玩家表現差（高難度）
def evaluate_strong(individual):
    sim_result = simulate_game_run(*individual)
    return evaluate_from_unity(individual, sim_result),

# 訓練弱殭屍：玩家表現好（低難度）
def evaluate_weak(individual):
    sim_result = simulate_game_run(*individual)
    score = evaluate_from_unity(individual, sim_result)
    return (-score,)

# A. 交配 (Mate)
toolbox.register("mate", tools.cxBlend, alpha=0.5)
# 應用裝飾：讓交配結果被 checkBounds 函式檢查和裁剪
toolbox.decorate("mate", checkBounds(*HP_BOUNDS))

# B. 突變 (Mutate)
# 突變 sigma 保持較小，避免一次跳出範圍太遠
toolbox.register("mutate", tools.mutGaussian, mu=0.0, sigma=0.2, indpb=0.1)
# 應用裝飾：讓突變結果被 checkBounds 函式檢查和裁剪
toolbox.decorate("mutate", checkBounds(*HP_BOUNDS))

# C. 選擇 (Select) - 不需要裁剪，因為它不改變基因
toolbox.register("select", tools.selTournament, tournsize=3)

def train_zombie(eval_func, save_path, label):
    toolbox.register("evaluate", eval_func)
    pop = toolbox.population(n=POP_SIZE)
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", np.mean)
    stats.register("min", np.min)

    print(f"訓練開始：{label}")
    pop, log = algorithms.eaSimple(pop, toolbox, cxpb=CX_PB, mutpb=MUT_PB,
                                   ngen=N_GEN, stats=stats, verbose=True)

    best = tools.selBest(pop, 1)[0]
    print(f"{label} 最佳參數：", best)
    with open(save_path, "wb") as f:
        pickle.dump({
            "HP_Mult": best[0],
            "ATK_Mult": best[1],
            "Det_Range": best[2],
            "Move_Speed": best[3]
        }, f)

if __name__ == "__main__":
    train_zombie(evaluate_strong, "P_Strong.pkl", "極強殭屍")
    train_zombie(evaluate_weak, "P_Weak.pkl", "極弱殭屍")
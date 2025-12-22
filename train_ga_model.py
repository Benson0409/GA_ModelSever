from deap import base, creator, tools, algorithms
import random
import numpy as np
import pickle
from model_core import simulate_game_run, evaluate_from_unity

# --- 基因範圍重新設定 (收縮邊界避免秒殺) ---
HP_BOUNDS = [0.7, 1.4]     # 血量最低 0.7 防止秒殺，最高 1.4 防止太坦
ATK_BOUNDS = [0.7, 1.4]    # 攻擊力收縮
DET_BOUNDS = [0.9, 1.1]    # 偵測範圍限制
SPEED_BOUNDS = [0.9, 1.1]  # 移動速度限制

POP_SIZE = 50
N_GEN = 60
CX_PB = 0.7
MUT_PB = 0.2

if not hasattr(creator, "FitnessMax"):
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMax)

toolbox = base.Toolbox()
toolbox.register("attr_hp_mult", random.uniform, *HP_BOUNDS)
toolbox.register("attr_atk_mult", random.uniform, *ATK_BOUNDS)
toolbox.register("attr_det_range", random.uniform, *DET_BOUNDS)
toolbox.register("attr_move_speed", random.uniform, *SPEED_BOUNDS)
toolbox.register("individual", tools.initCycle, creator.Individual,
                 (toolbox.attr_hp_mult, toolbox.attr_atk_mult, toolbox.attr_det_range, toolbox.attr_move_speed), n=1)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

def checkBounds():
    def decorator(func):
        def wrapper(*args, **kwargs):
            offspring = func(*args, **kwargs)
            for ind in offspring:
                ind[0] = np.clip(ind[0], *HP_BOUNDS)
                ind[1] = np.clip(ind[1], *ATK_BOUNDS)
                ind[2] = np.clip(ind[2], *DET_BOUNDS)
                ind[3] = np.clip(ind[3], *SPEED_BOUNDS)
            return offspring
        return wrapper
    return decorator

def evaluate_strong(individual):
    sim_result = simulate_game_run(*individual)
    score = evaluate_from_unity(individual, sim_result)
    return (-score,)

def evaluate_weak(individual):
    sim_result = simulate_game_run(*individual)
    return (evaluate_from_unity(individual, sim_result),)

toolbox.register("mate", tools.cxBlend, alpha=0.5)
toolbox.decorate("mate", checkBounds())
toolbox.register("mutate", tools.mutGaussian, mu=0.0, sigma=0.3, indpb=0.1)
toolbox.decorate("mutate", checkBounds())
toolbox.register("select", tools.selTournament, tournsize=3)

def train_zombie(eval_func, save_path, label):
    toolbox.register("evaluate", eval_func)
    pop = toolbox.population(n=POP_SIZE)
    algorithms.eaSimple(pop, toolbox, cxpb=CX_PB, mutpb=MUT_PB, ngen=N_GEN, verbose=False)
    best = tools.selBest(pop, 1)[0]
    print(f"✅ {label} 完成！最佳基因: HP={best[0]:.2f}, ATK={best[1]:.2f}, DET={best[2]:.2f}, SPD={best[3]:.2f}")
    with open(save_path, "wb") as f:
        pickle.dump({"HP_Mult": best[0], "ATK_Mult": best[1], "Det_Range": best[2], "Move_Speed": best[3]}, f)

if __name__ == "__main__":
    train_zombie(evaluate_strong, "P_Strong.pkl", "極強殭屍")
    train_zombie(evaluate_weak, "P_Weak.pkl", "極弱殭屍")
from flask import Flask, request, jsonify
from model_core import evaluate_from_unity, adjust_difficulty_dda
import pickle

app = Flask(__name__)

# 載入訓練好的強弱邊界參數（記得已經用 train_ga_model.py 建立過）
with open("P_Strong.pkl", "rb") as f:
    P_Strong = pickle.load(f)

with open("P_Weak.pkl", "rb") as f:
    P_Weak = pickle.load(f)

# 初始化預設參數（Unity 最初啟動時用）
CURRENT_PARAMS = {
    "HP_Mult": 1.0,
    "ATK_Mult": 1.0,
    "Det_Range": 1.0,
    "Move_Speed": 1.0
}

@app.route("/adjust_difficulty", methods=["POST"])
def adjust_difficulty():
    global CURRENT_PARAMS

    # 1. 接收玩家傳來的 JSON 數據
    player_data = request.get_json()

    # 2. 評估玩家表現
    score = evaluate_from_unity(
        list(CURRENT_PARAMS.values()), player_data
    )

    # 3. 執行難度調整
    new_params, action = adjust_difficulty_dda(
        CURRENT_PARAMS, player_data, P_Strong, P_Weak
    )

    CURRENT_PARAMS = new_params  # 更新狀態

    # 4. 回傳 JSON 給 Unity
    return jsonify({
        "adjusted_params": CURRENT_PARAMS,
        "evaluation_score": score,
        "adjustment_action": action
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
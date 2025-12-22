from flask import Flask, request, jsonify
from model_core import evaluate_from_unity, adjust_difficulty_dda
import pickle

app = Flask(__name__)

# 載入預設邊界
with open("P_Strong.pkl", "rb") as f: P_Strong = pickle.load(f)
with open("P_Weak.pkl", "rb") as f: P_Weak = pickle.load(f)

CURRENT_PARAMS = {"HP_Mult": 1.0, "ATK_Mult": 1.0, "Det_Range": 1.0, "Move_Speed": 1.0}
HAS_CALIBRATED = False  # 追蹤是否已進行進入實戰後的第一次校準


@app.route("/adjust_difficulty", methods=["POST"])
def adjust_difficulty():
    global CURRENT_PARAMS, HAS_CALIBRATED
    player_data = request.get_json()

    # 獲取場景標籤
    scene = player_data.get("scene_name", "Unknown")
    is_tut = (scene == "Tutorial")

    # 判斷是否為「進入實戰的第一次調用」
    is_first = False
    if not is_tut and not HAS_CALIBRATED:
        is_first = True
        HAS_CALIBRATED = True

    score = evaluate_from_unity(list(CURRENT_PARAMS.values()), player_data)

    # 呼叫更新後的 DDA 邏輯
    new_params, action = adjust_difficulty_dda(
        CURRENT_PARAMS, player_data, P_Strong, P_Weak,
        is_tutorial=is_tut, is_first_game=is_first
    )

    CURRENT_PARAMS = new_params
    return jsonify({"adjusted_params": CURRENT_PARAMS, "action": action})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
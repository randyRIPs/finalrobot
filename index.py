from flask import Flask, jsonify, render_template_string, request
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

from update_coastal_forecast import main as update_firebase

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>海象資料管理系統</title>
    <style>
        body {
            font-family: Arial, "Microsoft JhengHei", sans-serif;
            background: #0f172a;
            color: white;
            text-align: center;
            padding-top: 80px;
        }

        h1 {
            font-size: 36px;
        }

        p {
            color: #cbd5e1;
        }

        button {
            margin-top: 30px;
            padding: 16px 32px;
            font-size: 20px;
            border: none;
            border-radius: 10px;
            background: #38bdf8;
            color: #0f172a;
            cursor: pointer;
            font-weight: bold;
        }

        button:hover {
            background: #0ea5e9;
        }

        #result {
            margin: 30px auto;
            width: 80%;
            max-width: 700px;
            background: #1e293b;
            padding: 20px;
            border-radius: 10px;
            white-space: pre-wrap;
            text-align: left;
        }
    </style>
</head>
<body>

    <h1>海象資料管理系統</h1>
    <p>手動抓取中央氣象署資料，並更新 Firebase</p>

    <button onclick="updateData()">手動更新 Firebase</button>

    <div id="result">尚未執行更新</div>

    <script>
        async function updateData() {
            const result = document.getElementById("result");
            result.innerText = "更新中，請稍候...";

            try {
                const response = await fetch("/manual-update");
                const data = await response.json();

                result.innerText = JSON.stringify(data, null, 2);
            } catch (error) {
                result.innerText = "更新失敗：\\n" + error;
            }
        }
    </script>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML)


def get_db():
    if not firebase_admin._apps:

        if os.environ.get("serviceAccountKey"):
            firebase_json = json.loads(os.environ["serviceAccountKey"])
            cred = credentials.Certificate(firebase_json)

        else:
            cred = credentials.Certificate("serviceAccountKey.json")

        firebase_admin.initialize_app(cred)

    return firestore.client()


@app.route("/manual-update")
def manual_update():
    try:
        update_firebase()

        return jsonify({
            "status": "success",
            "message": "Firebase 更新完成"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json(force=True)

    city = (
        req.get("queryResult", {})
        .get("parameters", {})
        .get("city", "")
    )

    if isinstance(city, list):
        city = city[0] if city else ""

    if not city:
        return jsonify({
            "fulfillmentText": "請問要查詢哪個縣市？"
        })

    db = get_db()

    doc = (
        db.collection("coastal_forecast")
        .document(city)
        .get()
    )

    if not doc.exists:
        return jsonify({
            "fulfillmentText": f"我是羅翊綸的機器人\n\n找不到 {city} 的資料"
        })

    data = doc.to_dict()
    forecast = data.get("forecast", [])

    msg = "我是羅翊綸的機器人\n\n"
    msg += f"{city} 未來天氣預報\n\n"

    for day in forecast[:3]:
        display_date = day.get("displayDate", "")
        weather = day.get("weather", "")
        temp_min = day.get("tempMin", "")
        temp_max = day.get("tempMax", "")
        high_tide = day.get("highTide", [])
        low_tide = day.get("lowTide", [])

        msg += f"{display_date} {weather} {temp_min}~{temp_max}°C\n"

        if high_tide:
            msg += "滿潮：" + "、".join(high_tide) + "\n"

        if low_tide:
            msg += "乾潮：" + "、".join(low_tide) + "\n"

        msg += "\n"

    return jsonify({
        "fulfillmentText": msg
    })


if __name__ == "__main__":
    app.run(debug=True)
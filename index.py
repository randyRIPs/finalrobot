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
        h1 { font-size: 36px; }
        p { color: #cbd5e1; }
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
        button:hover { background: #0ea5e9; }
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


def get_city_from_context(req):
    contexts = (
        req.get("queryResult", {})
        .get("outputContexts", [])
    )

    for ctx in contexts:
        params = ctx.get("parameters", {})
        city = params.get("city")

        if city:
            if isinstance(city, list):
                return city[0]
            return city

    return ""


def get_forecast_doc(city):
    db = get_db()

    doc = (
        db.collection("coastal_forecast")
        .document(city)
        .get()
    )

    if not doc.exists:
        return None

    return doc.to_dict()


def build_date_menu(city, forecast):
    msg = "我是羅翊綸的機器人\n\n"
    msg += f"📍已選擇：{city}\n\n"
    msg += "請選擇想查詢的日期：\n\n"

    for i, day in enumerate(forecast[:7], start=1):
        display_date = day.get("displayDate", "")
        msg += f"{i}. {display_date}\n"

    msg += "\n請直接輸入日期，例如：06-12"
    return msg


def normalize_user_date(text):
    text = text.strip()
    text = text.replace("/", "-")

    if text in ["今天", "今日"]:
        return "INDEX_0"

    if text == "明天":
        return "INDEX_1"

    if text == "後天":
        return "INDEX_2"

    return text


def find_day_by_date(forecast, user_date):
    user_date = normalize_user_date(user_date)

    if user_date.startswith("INDEX_"):
        index = int(user_date.replace("INDEX_", ""))

        if index < len(forecast):
            return forecast[index]

        return None

    for day in forecast:
        display_date = day.get("displayDate", "")
        full_date = day.get("date", "")

        if user_date == display_date:
            return day

        if user_date == full_date:
            return day

    return None


def build_day_reply(city, day):
    msg = "我是羅翊綸的機器人\n\n"
    msg += f"📍{city}\n"
    msg += f"📅 {day.get('displayDate', '')}\n\n"
    msg += f"🌤️ 天氣：{day.get('weather', '')}\n"
    msg += f"🌡️ 溫度：{day.get('tempMin', '')}~{day.get('tempMax', '')}°C\n"

    wind_direction = day.get("windDirection", "")
    wind_speed = day.get("windSpeed", "")

    if wind_direction or wind_speed:
        msg += f"💨 風向風速：{wind_direction} {wind_speed}\n"

    high_tide = day.get("highTide", [])
    low_tide = day.get("lowTide", [])

    if high_tide:
        msg += "🌊 滿潮：" + "、".join(high_tide) + "\n"

    if low_tide:
        msg += "🏖️ 乾潮：" + "、".join(low_tide) + "\n"

    return msg


@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json(force=True)

    query_result = req.get("queryResult", {})
    intent_name = (
        query_result
        .get("intent", {})
        .get("displayName", "")
    )

    parameters = query_result.get("parameters", {})
    query_text = query_result.get("queryText", "")

    # 第一階段：使用者輸入縣市，回覆可選日期
    if intent_name == "WeatherForecast":
        city = parameters.get("city", "")

        if isinstance(city, list):
            city = city[0] if city else ""

        if not city:
            return jsonify({
                "fulfillmentText": "請問想查詢哪裡的天氣？"
            })

        data = get_forecast_doc(city)

        if data is None:
            return jsonify({
                "fulfillmentText": f"我是羅翊綸的機器人\n\n找不到 {city} 的資料"
            })

        forecast = data.get("forecast", [])

        if not forecast:
            return jsonify({
                "fulfillmentText": f"我是羅翊綸的機器人\n\n{city} 目前沒有預報資料"
            })

        msg = build_date_menu(city, forecast)

        return jsonify({
            "fulfillmentText": msg,
            "outputContexts": [
                {
                    "name": req["session"] + "/contexts/weather-followup",
                    "lifespanCount": 5,
                    "parameters": {
                        "city": city
                    }
                }
            ]
        })

    # 第二階段：使用者輸入日期，回覆指定日期資料
    if intent_name == "WeatherDateSelect":
        city = get_city_from_context(req)

        if not city:
            return jsonify({
                "fulfillmentText": "請先告訴我要查詢哪個縣市。"
            })

        user_date = parameters.get("date", "")

        if isinstance(user_date, list):
            user_date = user_date[0] if user_date else ""

        if not user_date:
            user_date = query_text

        data = get_forecast_doc(city)

        if data is None:
            return jsonify({
                "fulfillmentText": f"我是羅翊綸的機器人\n\n找不到 {city} 的資料"
            })

        forecast = data.get("forecast", [])
        target_day = find_day_by_date(forecast, user_date)

        if target_day is None:
            msg = "我是羅翊綸的機器人\n\n"
            msg += "找不到這個日期，請輸入以下其中一天：\n\n"

            for day in forecast[:7]:
                msg += f"{day.get('displayDate', '')}\n"

            return jsonify({
                "fulfillmentText": msg
            })

        msg = build_day_reply(city, target_day)

        return jsonify({
            "fulfillmentText": msg
        })

    return jsonify({
        "fulfillmentText": "我是羅翊綸的機器人\n\n我目前可以查詢縣市天氣與潮汐。"
    })


if __name__ == "__main__":
    app.run(debug=True)
from flask import jsonify
import os
import json
import urllib.parse
import urllib.request
import firebase_admin
from firebase_admin import credentials, firestore


CITY_LIST = [
    "台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市",
    "基隆市", "新竹市", "嘉義市",
    "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣",
    "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "台東縣",
    "澎湖縣", "金門縣", "連江縣"
]

# 朋友的一般天氣 / 穿搭 / 帶傘功能會用到的 intent 名稱
# 你 Dialogflow 裡面 intent 名稱如果不同，就加在這裡
OUTFIT_INTENTS = [
    "今日天氣查詢",
    "天氣查詢",
    "穿搭建議",
    "帶傘提醒",
    "活動建議",
    "weather.query",
    "outfit.suggest",
    "umbrella.check",
    "activity.suggest",
]

CITY_ALIASES = {
    "臺北": "台北市",
    "台北": "台北市",
    "新北": "新北市",
    "桃園": "桃園市",
    "臺中": "台中市",
    "台中": "台中市",
    "臺南": "台南市",
    "台南": "台南市",
    "高雄": "高雄市",
    "基隆": "基隆市",
    "新竹": "新竹市",
    "嘉義": "嘉義市",
    "苗栗": "苗栗縣",
    "彰化": "彰化縣",
    "南投": "南投縣",
    "雲林": "雲林縣",
    "屏東": "屏東縣",
    "宜蘭": "宜蘭縣",
    "花蓮": "花蓮縣",
    "臺東": "台東縣",
    "台東": "台東縣",
    "澎湖": "澎湖縣",
    "金門": "金門縣",
    "連江": "連江縣",
    "馬祖": "連江縣",
}

CWA_CITY_NAMES = {
    "台北市": "臺北市",
    "台中市": "臺中市",
    "台南市": "臺南市",
    "台東縣": "臺東縣",
}


# ==========================
# Firebase：你原本的海邊潮汐資料
# ==========================

def get_db():
    if not firebase_admin._apps:
        if os.environ.get("serviceAccountKey"):
            firebase_json = json.loads(os.environ["serviceAccountKey"])
            cred = credentials.Certificate(firebase_json)
        else:
            cred = credentials.Certificate("serviceAccountKey.json")

        firebase_admin.initialize_app(cred)

    return firestore.client()


def get_forecast_doc(city):
    db = get_db()
    doc = db.collection("coastal_forecast").document(city).get()

    if not doc.exists:
        return None

    return doc.to_dict()


# ==========================
# 共用小工具
# ==========================

def normalize_dialogflow_city(value):
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return (
            value.get("city")
            or value.get("admin-area")
            or value.get("subadmin-area")
            or ""
        )

    if isinstance(value, list) and value:
        return normalize_dialogflow_city(value[0])

    return ""


def extract_city_from_text(text, default_city="台中市"):
    text = str(text)

    for city in CITY_LIST:
        if city in text:
            return city

    for alias, city in CITY_ALIASES.items():
        if alias in text:
            return city

    return default_city


def get_city_from_context(req):
    contexts = req.get("queryResult", {}).get("outputContexts", [])

    for ctx in contexts:
        params = ctx.get("parameters", {})
        city = params.get("city")

        if city:
            if isinstance(city, list):
                return city[0]
            return city

    return ""


# ==========================
# 你的海邊天氣 + 潮汐功能：原本保留
# ==========================

def build_date_menu(city, coast, forecast):
    msg = "🌊 正在為你查詢未來一周海邊天氣與潮汐資訊\n\n"
    msg += f"📍查詢地區：{city}\n"

    if coast:
        msg += f"🏖️ 參考海岸：{coast}\n"

    msg += "\n📅 請選擇查詢日期：\n\n"

    for i, day in enumerate(forecast[:7], start=1):
        msg += f"{i}. {day.get('displayDate', '')}\n"

    msg += "\n請直接輸入日期，例如：06-14"

    return msg


def normalize_user_date(text):
    text = str(text).strip()
    text = text.replace("/", "-")

    if text in ["今天", "今日"]:
        return "INDEX_0"

    if text == "明天":
        return "INDEX_1"

    if text == "後天":
        return "INDEX_2"

    parts = text.split("-")

    if len(parts) == 2:
        month = parts[0].zfill(2)
        day = parts[1].zfill(2)
        return f"{month}-{day}"

    return text


def find_day_by_date(forecast, user_date):
    user_date = normalize_user_date(user_date)

    if user_date.startswith("INDEX_"):
        index = int(user_date.replace("INDEX_", ""))

        if index < len(forecast):
            return forecast[index]

        return None

    for day in forecast:
        if user_date == day.get("displayDate", ""):
            return day

        if user_date == day.get("date", ""):
            return day

    return None


def build_day_reply(city, coast, day):
    msg = f"📍{city}\n"

    if coast:
        msg += f"🏖️ {coast}\n"

    msg += f"\n📅 {day.get('displayDate', '')}\n\n"
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


def build_date_not_found_reply(forecast):
    msg = "找不到這個日期，請輸入以下其中一天：\n\n"

    for day in forecast[:7]:
        msg += f"{day.get('displayDate', '')}\n"

    return msg


def close_weather_context(req, message):
    return jsonify({
        "fulfillmentText": message,
        "outputContexts": [
            {
                "name": req["session"] + "/contexts/weather-followup",
                "lifespanCount": 0
            }
        ]
    })


def handle_weather_forecast(req, query_result):
    parameters = query_result.get("parameters", {})
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
            "fulfillmentText": f"找不到 {city} 的資料"
        })

    forecast = data.get("forecast", [])
    coast = data.get("coast", "")

    if not forecast:
        return jsonify({
            "fulfillmentText": f"{city} 目前沒有預報資料"
        })

    return jsonify({
        "fulfillmentText": build_date_menu(city, coast, forecast),
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


def handle_weather_date_select(req, query_result):
    parameters = query_result.get("parameters", {})
    query_text = query_result.get("queryText", "").strip()

    if query_text in CITY_LIST:
        fake_query_result = {
            "parameters": {
                "city": query_text
            }
        }

        return handle_weather_forecast(req, fake_query_result)

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
        return close_weather_context(
            req,
            f"找不到 {city} 的資料"
        )

    forecast = data.get("forecast", [])
    coast = data.get("coast", "")

    target_day = find_day_by_date(forecast, user_date)

    if target_day is None:
        return jsonify({
            "fulfillmentText": build_date_not_found_reply(forecast)
        })

    return close_weather_context(
        req,
        build_day_reply(city, coast, target_day)
    )


# ==========================
# 新增：朋友的一般天氣 / 穿搭 / 帶傘功能
# 不影響上面的海邊潮汐功能
# ==========================

def detect_outfit_intent(intent_name, text):
    text = str(text).strip()
    name = str(intent_name).strip().lower()

    if any(word in text for word in ["傘", "下雨", "雨"]):
        return "umbrella"

    if any(word in text for word in ["穿", "外套", "短袖", "長袖", "衣服", "穿搭"]):
        return "outfit"

    if any(word in text for word in ["跑步", "運動", "騎車", "曬衣", "出門玩", "活動"]):
        return "activity"

    mapping = {
        "今日天氣查詢": "weather",
        "天氣查詢": "weather",
        "weather.query": "weather",
        "穿搭建議": "outfit",
        "outfit.suggest": "outfit",
        "帶傘提醒": "umbrella",
        "umbrella.check": "umbrella",
        "活動建議": "activity",
        "activity.suggest": "activity",
    }

    for key, value in mapping.items():
        if key.lower() == name:
            return value

    return "weather"


def get_general_weather(city):
    api_key = os.environ.get("CWA_API_KEY", "")

    # 沒放中央氣象署 API key 時，先給範例資料，避免整支壞掉
    if not api_key:
        return {
            "city": city,
            "weather": "多雲午後短暫陣雨",
            "min_temp": 25,
            "max_temp": 31,
            "rain_probability": 60,
        }

    api_city = CWA_CITY_NAMES.get(city, city)
    query = urllib.parse.urlencode({
        "Authorization": api_key,
        "locationName": api_city,
    })
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?{query}"

    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        locations = payload.get("records", {}).get("location", [])
        if not locations:
            raise Exception("CWA no location data")

        elements = {
            item["elementName"]: item["time"][0]["parameter"]
            for item in locations[0].get("weatherElement", [])
        }

        return {
            "city": city,
            "weather": elements.get("Wx", {}).get("parameterName", "未知"),
            "min_temp": int(elements.get("MinT", {}).get("parameterName", 0)),
            "max_temp": int(elements.get("MaxT", {}).get("parameterName", 0)),
            "rain_probability": int(elements.get("PoP", {}).get("parameterName", 0)),
        }

    except Exception as error:
        print(f"一般天氣查詢失敗：{error}", flush=True)
        return {
            "city": city,
            "weather": "多雲午後短暫陣雨",
            "min_temp": 25,
            "max_temp": 31,
            "rain_probability": 60,
        }


def outfit_advice(weather):
    average_temp = round((weather["min_temp"] + weather["max_temp"]) / 2)

    if average_temp >= 30:
        base = "建議穿短袖、薄材質衣物，外出注意防曬與補水。"
    elif average_temp >= 24:
        base = "建議穿短袖或薄長袖，怕冷的話可以帶一件薄外套。"
    elif average_temp >= 18:
        base = "建議穿長袖或短袖加薄外套，早晚溫差要注意。"
    elif average_temp >= 15:
        base = "建議穿長袖加外套，騎車或晚上外出要再保暖一點。"
    else:
        base = "建議穿厚外套或保暖衣物，出門前可以加圍巾。"

    if weather["rain_probability"] >= 60:
        base += " 降雨機率偏高，鞋子建議選好走、防滑或不怕濕的款式。"

    return base


def umbrella_advice(weather):
    if weather["rain_probability"] >= 60:
        return "建議帶傘，今天下雨機率偏高。"

    if weather["rain_probability"] >= 30:
        return "可以帶摺疊傘，今天有機會下雨。"

    return "下雨機率不高，通常可以不用帶傘。"


def activity_advice(weather):
    if weather["rain_probability"] >= 60:
        return "今天較不適合長時間戶外活動，建議改成室內行程。"

    if weather["max_temp"] >= 32:
        return "可以活動，但天氣偏熱，建議避開中午並多補水。"

    return "今天整體適合外出活動，記得依體感調整衣物。"


def build_outfit_reply(intent, weather):
    summary = (
        f"{weather['city']}今日天氣：{weather['weather']}，"
        f"溫度約 {weather['min_temp']}-{weather['max_temp']} 度，"
        f"降雨機率 {weather['rain_probability']}%。"
    )

    if intent == "umbrella":
        return f"{summary}\n{umbrella_advice(weather)}"

    if intent == "outfit":
        return f"{summary}\n{outfit_advice(weather)}\n{umbrella_advice(weather)}"

    if intent == "activity":
        return f"{summary}\n{activity_advice(weather)}\n{umbrella_advice(weather)}"

    return f"{summary}\n{outfit_advice(weather)}"


def handle_outfit_bot(req, query_result):
    text = query_result.get("queryText", "")
    parameters = query_result.get("parameters", {})
    intent_name = query_result.get("intent", {}).get("displayName", "")

    city = normalize_dialogflow_city(
        parameters.get("city")
        or parameters.get("geo-city")
        or parameters.get("location")
    )

    if not city:
        city = extract_city_from_text(text, os.environ.get("DEFAULT_CITY", "台中市"))

    intent = detect_outfit_intent(intent_name, text)
    weather = get_general_weather(city)
    reply = build_outfit_reply(intent, weather)

    return jsonify({
        "fulfillmentText": reply
    })


# ==========================
# Dialogflow 總入口
# ==========================

def handle_dialogflow(req):
    query_result = req.get("queryResult", {})

    intent_name = (
        query_result
        .get("intent", {})
        .get("displayName", "")
    )

    # 你的原本功能：海邊天氣潮汐
    if intent_name == "WeatherForecast":
        return handle_weather_forecast(req, query_result)

    if intent_name == "WeatherDateSelect":
        return handle_weather_date_select(req, query_result)

    # 新增功能：朋友的一般天氣 / 穿搭 / 帶傘 / 活動建議
    if intent_name in OUTFIT_INTENTS:
        return handle_outfit_bot(req, query_result)

    return jsonify({
        "fulfillmentText": "我目前可以查詢縣市海邊天氣與潮汐，也可以查一般天氣、穿搭與帶傘建議。"
    })

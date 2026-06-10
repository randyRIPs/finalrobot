from dataclasses import dataclass


@dataclass
class WeatherInfo:
    city: str
    weather: str
    min_temp: int
    max_temp: int
    rain_probability: int
    comfort: str = ""


def detect_intent(text: str) -> str:
    text = text.strip()
    if any(word in text for word in ["傘", "下雨", "雨"]):
        return "umbrella"
    if any(word in text for word in ["穿", "外套", "短袖", "長袖", "衣服", "穿搭"]):
        return "outfit"
    if any(word in text for word in ["跑步", "運動", "騎車", "曬衣", "出門玩"]):
        return "activity"
    return "weather"


def normalize_intent(intent_name: str, text: str = "") -> str:
    name = intent_name.lower().strip()
    text_intent = detect_intent(text)
    if text_intent in {"outfit", "umbrella"}:
        return text_intent

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
    return detect_intent(text)


def extract_city(text: str, default_city: str = "台中市") -> str:
    cities = [
        "台北市",
        "新北市",
        "桃園市",
        "台中市",
        "台南市",
        "高雄市",
        "基隆市",
        "新竹市",
        "嘉義市",
        "新竹縣",
        "苗栗縣",
        "彰化縣",
        "南投縣",
        "雲林縣",
        "嘉義縣",
        "屏東縣",
        "宜蘭縣",
        "花蓮縣",
        "台東縣",
        "澎湖縣",
        "金門縣",
        "連江縣",
    ]
    aliases = {
        "臺北": "台北市",
        "台北": "台北市",
        "臺中": "台中市",
        "台中": "台中市",
        "臺南": "台南市",
        "台南": "台南市",
        "高雄": "高雄市",
        "新北": "新北市",
        "桃園": "桃園市",
        "新竹": "新竹市",
        "嘉義": "嘉義市",
    }
    for city in cities:
        if city in text:
            return city
    for alias, city in aliases.items():
        if alias in text:
            return city
    return default_city


def outfit_advice(weather: WeatherInfo) -> str:
    average_temp = round((weather.min_temp + weather.max_temp) / 2)
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

    if weather.rain_probability >= 60:
        base += " 降雨機率偏高，鞋子建議選好走、防滑或不怕濕的款式。"
    return base


def umbrella_advice(weather: WeatherInfo) -> str:
    if weather.rain_probability >= 60:
        return "建議帶傘，今天下雨機率偏高。"
    if weather.rain_probability >= 30:
        return "可以帶摺疊傘，今天有機會下雨。"
    return "下雨機率不高，通常可以不用帶傘。"


def activity_advice(weather: WeatherInfo) -> str:
    if weather.rain_probability >= 60:
        return "今天較不適合長時間戶外活動，建議改成室內行程。"
    if weather.max_temp >= 32:
        return "可以活動，但天氣偏熱，建議避開中午並多補水。"
    return "今天整體適合外出活動，記得依體感調整衣物。"


def build_reply(intent: str, weather: WeatherInfo) -> str:
    summary = (
        f"{weather.city}今日天氣：{weather.weather}，"
        f"溫度約 {weather.min_temp}-{weather.max_temp} 度，"
        f"降雨機率 {weather.rain_probability}%。"
    )
    if intent == "umbrella":
        return f"{summary}\n{umbrella_advice(weather)}"
    if intent == "outfit":
        return f"{summary}\n{outfit_advice(weather)}\n{umbrella_advice(weather)}"
    if intent == "activity":
        return f"{summary}\n{activity_advice(weather)}\n{umbrella_advice(weather)}"
    return f"{summary}\n{outfit_advice(weather)}"

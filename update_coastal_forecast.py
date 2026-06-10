import os
import json
from datetime import datetime

import requests
import urllib3
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

urllib3.disable_warnings()

# ==========================
# 基本設定
# ==========================

API_KEY = "rdec-key-123-45678-011121314"

WEATHER_DATASET = "F-D0047-091"
TIDE_DATASET = "F-A0021-001"

FIREBASE_COLLECTION = "coastal_forecast"
DAYS = 7

# 空 list = 抓全部縣市
TARGET_CITIES = []

CITY_ALIASES = {
    "台北市": ["台北市", "臺北市"],
    "新北市": ["新北市"],
    "桃園市": ["桃園市"],
    "台中市": ["台中市", "臺中市"],
    "台南市": ["台南市", "臺南市"],
    "高雄市": ["高雄市"],
    "基隆市": ["基隆市"],
    "新竹市": ["新竹市"],
    "嘉義市": ["嘉義市"],
    "新竹縣": ["新竹縣"],
    "苗栗縣": ["苗栗縣"],
    "彰化縣": ["彰化縣"],
    "南投縣": ["南投縣"],
    "雲林縣": ["雲林縣"],
    "嘉義縣": ["嘉義縣"],
    "屏東縣": ["屏東縣"],
    "宜蘭縣": ["宜蘭縣"],
    "花蓮縣": ["花蓮縣"],
    "台東縣": ["台東縣", "臺東縣"],
    "澎湖縣": ["澎湖縣"],
    "金門縣": ["金門縣"],
    "連江縣": ["連江縣"],
}

TIDE_KEYWORDS = {
    "台北市": ["台北", "臺北"],
    "新北市": ["新北", "淡水", "富貴角", "龍洞", "貢寮"],
    "桃園市": ["桃園", "竹圍"],
    "台中市": ["台中", "臺中", "台中港", "臺中港"],
    "台南市": ["台南", "臺南", "安平"],
    "高雄市": ["高雄", "永安", "興達", "旗津"],
    "基隆市": ["基隆"],
    "新竹市": ["新竹"],
    "嘉義市": ["嘉義"],
    "新竹縣": ["新竹", "新豐"],
    "苗栗縣": ["苗栗", "後龍", "通霄"],
    "彰化縣": ["彰化", "鹿港", "王功"],
    "南投縣": ["南投"],
    "雲林縣": ["雲林", "麥寮", "台西", "臺西"],
    "嘉義縣": ["嘉義", "東石", "布袋"],
    "屏東縣": ["屏東", "東港", "恆春", "後壁湖", "小琉球"],
    "宜蘭縣": ["宜蘭", "蘇澳", "烏石", "頭城"],
    "花蓮縣": ["花蓮", "石梯"],
    "台東縣": ["台東", "臺東", "成功", "蘭嶼", "綠島"],
    "澎湖縣": ["澎湖", "馬公"],
    "金門縣": ["金門", "料羅"],
    "連江縣": ["連江", "馬祖", "南竿", "北竿"],
}


def fetch_cwa_data(dataset_id):
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{dataset_id}"

    response = requests.get(
        url,
        params={
            "Authorization": API_KEY,
            "format": "JSON"
        },
        verify=False,
        timeout=60
    )

    response.raise_for_status()
    return response.json()


# ==========================
# Firebase
# ==========================

def init_firebase():
    if not firebase_admin._apps:

        if os.environ.get("serviceAccountKey"):
            firebase_json = json.loads(os.environ["serviceAccountKey"])
            cred = credentials.Certificate(firebase_json)

        else:
            cred = credentials.Certificate("serviceAccountKey.json")

        firebase_admin.initialize_app(cred)

    return firestore.client()


def normalize_city_name(name):
    name = name.replace("臺", "台")

    for standard_name, aliases in CITY_ALIASES.items():
        for alias in aliases:
            if name == alias.replace("臺", "台"):
                return standard_name

    return name


def get_element_value(time_item, key):
    values = time_item.get("ElementValue", [])

    if not values:
        return ""

    return values[0].get(key, "")


def get_all_weather_locations(weather_data):
    result = {}
    groups = weather_data.get("records", {}).get("Locations", [])

    for group in groups:
        locations = group.get("Location", [])

        for loc in locations:
            raw_name = loc.get("LocationName", "")
            city_name = normalize_city_name(raw_name)

            if not city_name:
                continue

            if TARGET_CITIES and city_name not in TARGET_CITIES:
                continue

            if city_name not in result:
                result[city_name] = loc

    return result


def find_tide_location(city_name, tide_data):
    keywords = TIDE_KEYWORDS.get(city_name, [city_name])
    forecasts = tide_data.get("records", {}).get("TideForecasts", [])

    for item in forecasts:
        location = item.get("Location", {})
        location_name = location.get("LocationName", "")
        normalized_location_name = location_name.replace("臺", "台")

        for keyword in keywords:
            normalized_keyword = keyword.replace("臺", "台")

            if normalized_keyword in normalized_location_name:
                return item

    return None


def fill_element(forecast, elements, element_name, value_key, output_key):
    if element_name not in elements:
        return

    times = elements[element_name].get("Time", [])

    for i, t in enumerate(times[:len(forecast)]):
        forecast[i][output_key] = get_element_value(t, value_key)


def build_weather_forecast(weather_location):
    elements = {}

    for item in weather_location.get("WeatherElement", []):
        element_name = item.get("ElementName", "")
        elements[element_name] = item

    if "天氣現象" not in elements:
        raise Exception("找不到天氣現象資料")

    forecast = []
    used_dates = set()

    weather_times = elements["天氣現象"].get("Time", [])

    for t in weather_times:
        date = t.get("StartTime", "")[:10]

        if not date:
            continue

        if date in used_dates:
            continue

        used_dates.add(date)

        forecast.append({
            "date": date,
            "displayDate": date[5:],
            "weather": get_element_value(t, "Weather"),
            "tempMin": "",
            "tempMax": "",
            "windDirection": "",
            "windSpeed": "",
            "highTide": [],
            "lowTide": []
        })

        if len(forecast) >= DAYS:
            break

    fill_element_by_date(forecast, elements, "最高溫度", "MaxTemperature", "tempMax")
    fill_element_by_date(forecast, elements, "最低溫度", "MinTemperature", "tempMin")
    fill_element_by_date(forecast, elements, "風向", "WindDirection", "windDirection")
    fill_element_by_date(forecast, elements, "風速", "WindSpeed", "windSpeed")

    return forecast

def fill_element_by_date(forecast, elements, element_name, value_key, output_key):
    if element_name not in elements:
        return

    date_map = {}

    for t in elements[element_name].get("Time", []):
        date = t.get("StartTime", "")[:10]

        if date and date not in date_map:
            date_map[date] = get_element_value(t, value_key)

    for day in forecast:
        date = day.get("date", "")

        if date in date_map:
            day[output_key] = date_map[date]


def add_tide_to_forecast(city_name, forecast, tide_data):
    target_tide = find_tide_location(city_name, tide_data)

    if target_tide is None:
        return forecast, ""

    tide_location = target_tide.get("Location", {})
    coast_name = tide_location.get("LocationName", "")

    daily_list = (
        tide_location
        .get("TimePeriods", {})
        .get("Daily", [])
    )

    tide_map = {}

    for day in daily_list:
        date = day.get("Date", "")

        if date:
            tide_map[date] = day

    for day in forecast:
        date = day.get("date", "")

        if date not in tide_map:
            continue

        tide_times = tide_map[date].get("Time", [])

        for tide in tide_times:
            date_time = tide.get("DateTime", "")
            tide_type = tide.get("Tide", "")

            time_str = date_time[11:16] if len(date_time) >= 16 else date_time

            if tide_type == "滿潮":
                day["highTide"].append(time_str)

            elif tide_type == "乾潮":
                day["lowTide"].append(time_str)

    return forecast, coast_name


def main():
    print("開始下載天氣資料...")
    weather_data = fetch_cwa_data(WEATHER_DATASET)

    print("開始下載潮汐資料...")
    tide_data = fetch_cwa_data(TIDE_DATASET)

    print("開始初始化 Firebase...")
    db = init_firebase()

    weather_locations = get_all_weather_locations(weather_data)

    if not weather_locations:
        raise Exception("找不到任何縣市天氣資料")

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    success_count = 0
    fail_count = 0

    for city_name, weather_location in weather_locations.items():

        try:
            forecast = build_weather_forecast(weather_location)

            forecast, coast_name = add_tide_to_forecast(
                city_name,
                forecast,
                tide_data
            )

            doc = {
                "city": city_name,
                "coast": coast_name,
                "forecast": forecast,
                "updatedAt": updated_at
            }

            db.collection(FIREBASE_COLLECTION).document(city_name).set(doc)

            success_count += 1

            if coast_name:
                print(f"完成：{city_name} / 潮汐站：{coast_name}")
            else:
                print(f"完成：{city_name} / 無潮汐資料")

        except Exception as e:
            fail_count += 1
            print(f"失敗：{city_name}，原因：{e}")

    print("====================")
    print(f"全部完成，成功 {success_count} 筆，失敗 {fail_count} 筆")


if __name__ == "__main__":
    main()
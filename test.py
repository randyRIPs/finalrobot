# update_port_fishing.py
import requests
import urllib3
from datetime import datetime
from bs4 import BeautifulSoup

import firebase_admin
from firebase_admin import credentials, firestore

urllib3.disable_warnings()

# ===== Firebase 初始化 =====
cred = credentials.Certificate("serviceAccountKey.json")

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

BASE = "https://fishing.twport.com.tw/PWA"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fishing.twport.com.tw/PWA/",
    "X-Requested-With": "XMLHttpRequest",
}

PORT_ALIASES = {
    "基隆": "基隆港",
    "基隆港": "基隆港",

    "台中": "臺中港",
    "臺中": "臺中港",
    "台中港": "臺中港",
    "臺中港": "臺中港",
    "北堤": "臺中港",
    "台中北堤": "臺中港",
    "臺中北堤": "臺中港",
    "北防波堤": "臺中港",

    "高雄": "高雄港",
    "高雄港": "高雄港",

    "安平": "安平港",
    "安平港": "安平港",

    "布袋": "布袋港",
    "布袋港": "布袋港",

    "花蓮": "花蓮港",
    "花蓮港": "花蓮港",
}


def clean_html(html_text):
    if not html_text:
        return ""

    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text("\n", strip=True)
    return text


def get_ports():
    url = BASE + "/locations/port"

    r = requests.get(
        url,
        headers=HEADERS,
        verify=False,
        timeout=20
    )

    r.raise_for_status()
    data = r.json()

    ports = []

    for item in data.get("data", {}).get("content", []):
        ports.append(item.get("port"))

    return ports


def get_regions(port):
    url = BASE + "/locations/region"

    r = requests.get(
        url,
        headers=HEADERS,
        params={"port": port},
        verify=False,
        timeout=20
    )

    r.raise_for_status()
    data = r.json()

    regions = []

    for item in data.get("data", {}).get("content", []):
        regions.append(item)

    return regions


def parse_status(item):
    text = str(item)

    if "暫停" in text or "關閉" in text or "不開放" in text:
        return "暫停開放"

    if "開放" in text:
        return "開放"

    return "未明確"


def save_to_firebase(spots):
    batch = db.batch()

    for spot in spots:
        doc_id = spot["spot_name"].replace("/", "_").replace(" ", "_")
        ref = db.collection("port_fishing_spots").document(doc_id)
        batch.set(ref, spot)

    for alias, port_name in PORT_ALIASES.items():
        ref = db.collection("port_fishing_aliases").document(alias)
        batch.set(ref, {
            "alias": alias,
            "port_name": port_name
        })

    batch.commit()


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("開始抓取官方商港垂釣 API...")

    ports = get_ports()
    print("港口：", ports)

    all_spots = []

    for port in ports:
        print(f"\n抓取 {port} 垂釣區...")

        regions = get_regions(port)

        for item in regions:
            spot_name = (
                item.get("region")
                or item.get("location")
                or item.get("name")
                or item.get("title")
                or f"{port}垂釣區"
            )

            note = clean_html(
                item.get("content")
                or item.get("description")
                or item.get("notice")
                or ""
            )

            spot = {
                "port_name": port,
                "spot_name": spot_name,
                "status": parse_status(item),
                "note": note,
                "raw_data": item,
                "source_url": "https://fishing.twport.com.tw/PWA/current",
                "updated_at": now
            }

            all_spots.append(spot)

            print(f"{port}｜{spot_name}｜{spot['status']}")

    save_to_firebase(all_spots)

    print(f"\n完成更新，共寫入 {len(all_spots)} 筆官方商港垂釣資料")


if __name__ == "__main__":
    main()
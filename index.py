from flask import Flask, jsonify, render_template_string, request

from update_coastal_forecast import main as update_coastal_forecast
from test import main as update_port_fishing
from dialogflow_webhook import handle_dialogflow

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>海象資料管理系統</title>
</head>
<body>
    <h1>海象資料管理系統</h1>
    <p>手動更新海邊天氣潮汐 + 商港垂釣資料</p>

    <button onclick="updateData()">手動更新全部資料</button>

    <pre id="result">尚未執行更新</pre>

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


@app.route("/manual-update")
def manual_update():
    try:
        update_coastal_forecast()
        update_port_fishing()

        return jsonify({
            "status": "success",
            "message": "海邊天氣潮汐 + 商港垂釣資料更新完成"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json(force=True)
    return handle_dialogflow(req)


if __name__ == "__main__":
    app.run(debug=True)
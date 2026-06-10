from flask import Flask, jsonify, render_template_string
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


if __name__ == "__main__":
    app.run(debug=True)
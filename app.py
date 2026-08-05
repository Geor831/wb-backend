from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
import os

app = Flask(__name__)
CORS(app)

# Токен Apify (можно задать через переменную окружения)
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "apify_api_Ps05va0Yzzu8YRANSeegUm82eevQSq28w3Jb")

@app.route('/api/apify', methods=['GET'])
def get_product():
    article = request.args.get('article')
    if not article:
        return jsonify({"error": "Не указан артикул"}), 400
    
    try:
        # 1. Запускаем актор
        run_url = f"https://api.apify.com/v2/acts/getascraper~wildberries-scraper/runs?token={APIFY_TOKEN}"
        input_data = {
            "searchQueries": [],
            "nmIds": [int(article)],
            "maxItems": 1,
            "region": "MOSCOW",
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }
        run_response = requests.post(run_url, json=input_data)
        if run_response.status_code != 200:
            return jsonify({"error": "Не удалось запустить актор"}), 500
        run_data = run_response.json()
        run_id = run_data['data']['id']
        
        # 2. Ждём завершения (до 30 секунд)
        status = "RUNNING"
        attempts = 0
        while status != "SUCCEEDED" and attempts < 15:
            time.sleep(2)
            status_url = f"https://api.apify.com/v2/acts/getascraper~wildberries-scraper/runs/{run_id}?token={APIFY_TOKEN}"
            status_response = requests.get(status_url)
            status_data = status_response.json()
            status = status_data['data']['status']
            attempts += 1
        
        if status != "SUCCEEDED":
            return jsonify({"error": "Актор не завершился успешно"}), 500
        
        # 3. Получаем данные
        dataset_url = f"https://api.apify.com/v2/datasets/{run_id}/items?token={APIFY_TOKEN}"
        dataset_response = requests.get(dataset_url)
        data = dataset_response.json()
        
        if not data:
            return jsonify({"error": "Товар не найден"}), 404
        
        # Если пришёл список, берём первый элемент
        if isinstance(data, list) and len(data) > 0:
            return jsonify(data[0])
        else:
            return jsonify(data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run()

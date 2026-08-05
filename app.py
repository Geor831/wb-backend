import os
import json
import time
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Токены из переменных окружения (безопасно!)
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "apify_api_Ps05va0Yzzu8YRANSeegUm82eevQSq28w3Jb")
AITUNNEL_TOKEN = os.environ.get("AITUNNEL_TOKEN", "sk-aitunnel-mAZ89Pdr1elwujJMKcMQ7ChEsODz0OFk")

@app.route('/health', methods=['GET'])
def health():
    """Проверка работоспособности для Railway"""
    return jsonify({"status": "ok"}), 200

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
        run_response = requests.post(run_url, json=input_data, timeout=30)
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
            status_response = requests.get(status_url, timeout=10)
            status_data = status_response.json()
            status = status_data['data']['status']
            attempts += 1

        if status != "SUCCEEDED":
            return jsonify({"error": "Актор не завершился успешно"}), 500

        # 3. Получаем данные
        dataset_url = f"https://api.apify.com/v2/datasets/{run_id}/items?token={APIFY_TOKEN}"
        dataset_response = requests.get(dataset_url, timeout=10)
        data = dataset_response.json()

        if not data:
            return jsonify({"error": "Товар не найден"}), 404

        # Возвращаем первый объект, если пришёл массив
        if isinstance(data, list) and len(data) > 0:
            return jsonify(data[0])
        else:
            return jsonify(data)

    except requests.exceptions.Timeout:
        return jsonify({"error": "Превышено время ожидания ответа от Apify"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search', methods=['GET'])
def search_products():
    """Заглушка для поиска (можно будет реализовать позже)"""
    query = request.args.get('q', '')
    # Пока возвращаем пустой список, чтобы не ломать фронтенд
    return jsonify({"products": []}), 200

if __name__ == '__main__':
    # Railway передаёт порт через переменную PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

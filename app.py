from flask import Flask, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

@app.route('/api/analyze/<int:article>')
def analyze(article):
    try:
        url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={article}"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return jsonify({"error": "Не удалось получить данные"}), 500
        data = response.json()
        product = data.get('data', {}).get('products', [])
        if not product:
            return jsonify({"error": "Товар не найден"}), 404
        return jsonify({"product": product[0]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
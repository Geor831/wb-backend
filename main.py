import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return FileResponse("index.html")

class ArticleRequest(BaseModel):
    article: str

def parse_wb_link(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        print(f"🔍 Парсим WB: {url}")
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"   WB статус: {resp.status_code}")
        if resp.status_code != 200:
            return {"error": f"WB вернул статус {resp.status_code}"}
        html = resp.text
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
        if not match:
            match = re.search(r'<script>window\.__INITIAL_STATE__\s*=\s*({.*?});</script>', html)
        if match:
            data_str = match.group(1)
            try:
                data = json.loads(data_str)
                if 'props' in data and 'pageProps' in data['props']:
                    page_props = data['props']['pageProps']
                    product = page_props.get('product', {})
                    if product:
                        name = product.get('name')
                        price = product.get('priceU') / 100 if product.get('priceU') else None
                        rating = product.get('rating')
                        feedbacks = product.get('feedbacks')
                        seller = product.get('seller', {}).get('name')
                        print("   WB: товар найден!")
                        return {
                            "name": name,
                            "price": price,
                            "rating": rating,
                            "feedbacks": feedbacks,
                            "seller": seller
                        }
                elif 'catalog' in data:
                    product_data = data.get('catalog', {}).get('product', {})
                    if product_data:
                        name = product_data.get('name')
                        price = product_data.get('priceU') / 100 if product_data.get('priceU') else None
                        rating = product_data.get('rating')
                        feedbacks = product_data.get('feedbacks')
                        seller = product_data.get('seller', {}).get('name')
                        print("   WB: товар найден!")
                        return {
                            "name": name,
                            "price": price,
                            "rating": rating,
                            "feedbacks": feedbacks,
                            "seller": seller
                        }
                print("   WB: товар не найден в JSON")
                return {"error": "Товар не найден в JSON-данных"}
            except json.JSONDecodeError as e:
                print(f"   WB: ошибка парсинга JSON: {e}")
                return {"error": f"Ошибка парсинга JSON: {e}"}
        print("   WB: не найден блок с JSON")
        return {"error": "Не найден блок с JSON-данными"}
    except Exception as e:
        print(f"   WB: исключение {e}")
        return {"error": f"Исключение WB: {str(e)}"}

def search_ozon(query: str):
    try:
        print(f"🔍 Ищем на Ozon: {query}")
        url = f"https://api.ozon.ru/composer-api.bx/_action/search?q={query}"
        resp = requests.get(url, timeout=10)
        print(f"   Ozon статус: {resp.status_code}")
        if resp.status_code != 200:
            return {"error": f"Ozon вернул статус {resp.status_code}"}
        data = resp.json()
        items = data.get('items', [])
        print(f"   Ozon: найдено {len(items)} товаров")
        if not items:
            return {"error": "Ozon не нашёл товары"}
        product = items[0]
        price = product.get('price', 0) / 100 if product.get('price') else 0
        return {
            "name": product.get('title', ''),
            "price": price,
            "rating": product.get('rating', 0),
            "feedbacks": product.get('reviews_count', 0),
            "seller": product.get('seller', {}).get('name', '')
        }
    except Exception as e:
        print(f"   Ozon: исключение {e}")
        return {"error": f"Исключение Ozon: {str(e)}"}

@app.post("/api/analyze-article")
async def analyze_article(req: ArticleRequest):
    query = req.article.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Пустой запрос")

    if 'wildberries.ru' in query:
        result = parse_wb_link(query)
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    result = search_ozon(query)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

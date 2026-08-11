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
    article: str  # оставляем имя article, чтобы не менять интерфейс

def parse_wb_link(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
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
                        return {
                            "name": name,
                            "price": price,
                            "rating": rating,
                            "feedbacks": feedbacks,
                            "seller": seller
                        }
            except json.JSONDecodeError:
                pass
        return None
    except:
        return None

def search_ozon(query: str):
    try:
        url = f"https://api.ozon.ru/composer-api.bx/_action/search?q={query}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        items = data.get('items', [])
        if not items:
            return None
        product = items[0]
        price = product.get('price', 0) / 100 if product.get('price') else 0
        return {
            "name": product.get('title', ''),
            "price": price,
            "rating": product.get('rating', 0),
            "feedbacks": product.get('reviews_count', 0),
            "seller": product.get('seller', {}).get('name', '')
        }
    except:
        return None

@app.post("/api/analyze-article")
async def analyze_article(req: ArticleRequest):
    query = req.article.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Пустой запрос")

    if 'wildberries.ru' in query:
        product = parse_wb_link(query)
        if not product:
            raise HTTPException(status_code=404, detail="Не удалось получить данные с Wildberries")
        return product

    product = search_ozon(query)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден на Ozon")
    return product

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

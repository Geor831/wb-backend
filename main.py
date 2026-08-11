import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bs4 import BeautifulSoup
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
    query: str

def parse_wb_link(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
        name_tag = soup.find('h1', class_='product-page__title')
        name = name_tag.text.strip() if name_tag else None
        price_script = soup.find('script', text=re.compile(r'"price":"\d+"'))
        price = None
        if price_script:
            match = re.search(r'"price":"(\d+)"', price_script.text)
            if match:
                price = int(match.group(1)) / 100
        rating_span = soup.find('span', class_='product-review__rating')
        rating = float(rating_span.text.replace(',', '.')) if rating_span else None
        reviews_span = soup.find('span', class_='product-review__count')
        feedbacks = int(reviews_span.text.replace(' ', '')) if reviews_span else 0
        seller_span = soup.find('span', class_='product-page__seller-name')
        seller = seller_span.text.strip() if seller_span else None
        return {
            "name": name,
            "price": price,
            "rating": rating,
            "feedbacks": feedbacks,
            "seller": seller
        }
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
    query = req.query.strip()
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

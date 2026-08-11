import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bs4 import BeautifulSoup
import re
import json

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
    article: str  # теперь это может быть ссылка

def parse_wb_link(url: str):
    """Парсит страницу Wildberries"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return {"error": f"Страница не загружена, статус {resp.status_code}"}
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Ищем название
        name_tag = soup.find('h1', class_='product-page__title')
        name = name_tag.text.strip() if name_tag else None
        # Ищем цену (в JSON-данных)
        price_script = soup.find('script', text=re.compile(r'"priceU":\d+'))
        price = None
        if price_script:
            match = re.search(r'"priceU":(\d+)', price_script.text)
            if match:
                price = int(match.group(1)) / 100
        # Рейтинг
        rating_span = soup.find('span', class_='product-review__rating')
        rating = float(rating_span.text.replace(',', '.')) if rating_span else None
        # Отзывы
        reviews_span = soup.find('span', class_='product-review__count')
        feedbacks = int(reviews_span.text.replace(' ', '')) if reviews_span else 0
        # Продавец
        seller_span = soup.find('span', class_='product-page__seller-name')
        seller = seller_span.text.strip() if seller_span else None
        if not any([name, price, rating, feedbacks, seller]):
            return {"error": "Не удалось извлечь данные (возможно, страница изменилась)"}
        return {
            "name": name,
            "price": price,
            "rating": rating,
            "feedbacks": feedbacks,
            "seller": seller
        }
    except Exception as e:
        return {"error": f"Ошибка при парсинге WB: {str(e)}"}

def parse_ozon_link(url: str):
    """Парсит страницу Ozon"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return {"error": f"Страница не загружена, статус {resp.status_code}"}
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Название
        name_tag = soup.find('h1', class_='product-title')
        if not name_tag:
            name_tag = soup.find('h1', class_='product-heading')
        name = name_tag.text.strip() if name_tag else None
        # Цена (ищем в JSON или в тегах)
        price_tag = soup.find('span', class_='price-value')
        if price_tag:
            price_text = price_tag.text.replace(' ', '').replace('₽', '').strip()
            price = float(price_text) if price_text else None
        else:
            # Ищем в JSON-данных
            script = soup.find('script', text=re.compile(r'"price":"\d+"'))
            if script:
                match = re.search(r'"price":"(\d+)"', script.text)
                if match:
                    price = int(match.group(1)) / 100
                else:
                    price = None
            else:
                price = None
        # Рейтинг
        rating_span = soup.find('span', class_='rating-score')
        if rating_span:
            rating_text = rating_span.text.replace(',', '.').strip()
            rating = float(rating_text) if rating_text else None
        else:
            rating = None
        # Отзывы
        reviews_span = soup.find('span', class_='reviews-count')
        if reviews_span:
            feedbacks = int(reviews_span.text.replace(' ', '').replace('(', '').replace(')', '')) if reviews_span.text else 0
        else:
            feedbacks = 0
        # Продавец (на Ozon продавец часто в JSON)
        seller = None
        seller_script = soup.find('script', text=re.compile(r'"sellerName":"[^"]+"'))
        if seller_script:
            match = re.search(r'"sellerName":"([^"]+)"', seller_script.text)
            if match:
                seller = match.group(1)
        if not any([name, price, rating, feedbacks, seller]):
            return {"error": "Не удалось извлечь данные (возможно, страница изменилась)"}
        return {
            "name": name,
            "price": price,
            "rating": rating,
            "feedbacks": feedbacks,
            "seller": seller
        }
    except Exception as e:
        return {"error": f"Ошибка при парсинге Ozon: {str(e)}"}

@app.post("/api/analyze-article")
async def analyze_article(req: ArticleRequest):
    query = req.article.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Пустой запрос")

    # Определяем, ссылка на какой маркетплейс
    if 'wildberries.ru' in query:
        result = parse_wb_link(query)
    elif 'ozon.ru' in query:
        result = parse_ozon_link(query)
    else:
        # Если это не ссылка, пробуем искать на Ozon (но это не будет работать из-за блокировок)
        # Для простоты возвращаем ошибку
        raise HTTPException(status_code=400, detail="Пожалуйста, вставьте ссылку на товар с Wildberries или Ozon")

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

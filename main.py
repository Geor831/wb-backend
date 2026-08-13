import os
import asyncio
import re
import json
import requests
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("AITUNNEL_KEY")
if not API_KEY:
    raise RuntimeError("❌ AITUNNEL_KEY не найден в .env. Создайте файл .env и добавьте AITUNNEL_KEY=ваш_ключ")
BASE_URL = "https://api.aitunnel.ru/v1"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================================
# 1. СТАТИЧЕСКИЕ СТРАНИЦЫ (без логотипа)
# ========================================================
@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/offer.html")
async def offer():
    return FileResponse("offer.html")

@app.get("/requisites.html")
async def requisites():
    return FileResponse("requisites.html")

@app.get("/success.html")
async def success():
    return FileResponse("success.html")

# ========================================================
# 2. МОДЕЛИ ДАННЫХ
# ========================================================
class ArticleRequest(BaseModel):
    article: str

class GenerateImageRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    model: str = "flux-3"

class GenerateVideoRequest(BaseModel):
    prompt: str
    source_video_url: str | None = None
    duration: int = 4
    size: str = "854x480"
    model: str = "seedance-2.5"

# ========================================================
# 3. ПАРСИНГ WILDBERRIES / OZON
# ========================================================
def parse_wb_link(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return {"error": f"Статус {resp.status_code}"}
        soup = BeautifulSoup(resp.text, 'html.parser')
        name_tag = soup.find('h1', class_='product-page__title')
        name = name_tag.text.strip() if name_tag else None
        price_script = soup.find('script', text=re.compile(r'"priceU":\d+'))
        price = None
        if price_script:
            match = re.search(r'"priceU":(\d+)', price_script.text)
            if match:
                price = int(match.group(1)) / 100
        rating_span = soup.find('span', class_='product-review__rating')
        rating = float(rating_span.text.replace(',', '.')) if rating_span else None
        reviews_span = soup.find('span', class_='product-review__count')
        feedbacks = int(reviews_span.text.replace(' ', '')) if reviews_span else 0
        seller_span = soup.find('span', class_='product-page__seller-name')
        seller = seller_span.text.strip() if seller_span else None
        if not any([name, price, rating, feedbacks, seller]):
            return {"error": "Не удалось извлечь данные"}
        return {"name": name, "price": price, "rating": rating, "feedbacks": feedbacks, "seller": seller}
    except Exception as e:
        return {"error": f"Ошибка WB: {str(e)}"}

def parse_ozon_link(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return {"error": f"Статус {resp.status_code}"}
        soup = BeautifulSoup(resp.text, 'html.parser')
        name_tag = soup.find('h1', class_='product-title') or soup.find('h1', class_='product-heading')
        name = name_tag.text.strip() if name_tag else None
        price_tag = soup.find('span', class_='price-value')
        if price_tag:
            price_text = price_tag.text.replace(' ', '').replace('₽', '').strip()
            price = float(price_text) if price_text else None
        else:
            script = soup.find('script', text=re.compile(r'"price":"\d+"'))
            if script:
                match = re.search(r'"price":"(\d+)"', script.text)
                price = int(match.group(1)) / 100 if match else None
            else:
                price = None
        rating_span = soup.find('span', class_='rating-score')
        rating = float(rating_span.text.replace(',', '.')) if rating_span else None
        reviews_span = soup.find('span', class_='reviews-count')
        feedbacks = int(reviews_span.text.replace(' ', '').replace('(', '').replace(')', '')) if reviews_span else 0
        seller = None
        seller_script = soup.find('script', text=re.compile(r'"sellerName":"[^"]+"'))
        if seller_script:
            match = re.search(r'"sellerName":"([^"]+)"', seller_script.text)
            if match:
                seller = match.group(1)
        if not any([name, price, rating, feedbacks, seller]):
            return {"error": "Не удалось извлечь данные"}
        return {"name": name, "price": price, "rating": rating, "feedbacks": feedbacks, "seller": seller}
    except Exception as e:
        return {"error": f"Ошибка Ozon: {str(e)}"}

@app.post("/api/analyze-article")
async def analyze_article(req: ArticleRequest):
    query = req.article.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Пустой запрос")
    if 'wildberries.ru' in query:
        result = parse_wb_link(query)
    elif 'ozon.ru' in query:
        result = parse_ozon_link(query)
    else:
        try:
            article_int = int(query)
            wb_url = f"https://www.wildberries.ru/catalog/{article_int}/detail.aspx"
            result = parse_wb_link(wb_url)
        except ValueError:
            raise HTTPException(status_code=400, detail="Введите ссылку или артикул")
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# ========================================================
# 4. ГЕНЕРАЦИЯ ЧЕРЕЗ AITUNNEL
# ========================================================
async def generate_with_aitunnel(endpoint: str, payload: dict, timeout_seconds: int = 120):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(f"{BASE_URL}/{endpoint}", json=payload, headers=headers)
        resp.raise_for_status()
        job = resp.json()
        while job["status"] not in ("completed", "failed"):
            await asyncio.sleep(5)
            resp = await client.get(job["polling_url"], headers=headers)
            resp.raise_for_status()
            job = resp.json()
        if job["status"] == "failed":
            raise Exception(job.get("error", "Generation failed"))
        return {"url": job["unsigned_urls"][0], "job_id": job["id"]}

@app.post("/api/generate-image")
async def generate_image(req: GenerateImageRequest):
    try:
        payload = {"model": req.model, "prompt": req.prompt, "size": req.size}
        result = await generate_with_aitunnel("images", payload)
        return {"success": True, "image_url": result["url"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-video")
async def generate_video(req: GenerateVideoRequest):
    try:
        payload = {"model": req.model, "prompt": req.prompt, "size": req.size, "duration": req.duration}
        if req.source_video_url:
            payload["input_references"] = [{"type": "video_url", "video_url": {"url": req.source_video_url}}]
        result = await generate_with_aitunnel("videos", payload)
        return {"success": True, "video_url": result["url"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========================================================
# 5. ЗАПУСК
# ========================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

import os
import time
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

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

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "apify_api_Ps05va0Yzzu8YRANSeegUm82eevQSq28w3Jb")

class ArticleRequest(BaseModel):
    article: str

# Словарь для преобразования артикула в поисковый запрос
ARTICLE_TO_SEARCH = {
    "61472739": "VeganNova кокосовые сливки",
    "157065568": "гофрокороб 600x400x400",  # пример
}

@app.post("/api/analyze-article")
async def analyze_article(req: ArticleRequest):
    if not APIFY_API_TOKEN:
        raise HTTPException(status_code=500, detail="APIFY_API_TOKEN не настроен")
    try:
        # Получаем поисковый запрос из словаря или используем сам артикул
        search_query = ARTICLE_TO_SEARCH.get(req.article, req.article)
        
        run_input = {
            "search": search_query,
            "maxResults": 1
        }
        headers = {
            "Authorization": f"Bearer {APIFY_API_TOKEN}",
            "Content-Type": "application/json"
        }
        resp = requests.post(
            "https://api.apify.com/v2/acts/getascraper~wildberries-scraper/runs",
            headers=headers,
            json=run_input,
            timeout=30
        )
        if resp.status_code != 201:
            raise Exception(f"Ошибка запуска актора: {resp.text}")
        run_data = resp.json()
        run_id = run_data['data']['id']
        dataset_id = run_data['data']['defaultDatasetId']

        for _ in range(20):
            status_resp = requests.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                headers=headers,
                timeout=10
            )
            if status_resp.status_code != 200:
                raise Exception("Ошибка получения статуса")
            status_json = status_resp.json()
            status = status_json['data']['status']
            if status == 'SUCCEEDED':
                break
            if status in ['FAILED', 'ABORTED']:
                raise Exception(f"Задача завершилась с {status}")
            time.sleep(2)
        else:
            raise Exception("Таймаут ожидания выполнения задачи")

        items_resp = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json",
            headers=headers,
            timeout=10
        )
        if items_resp.status_code != 200:
            raise Exception("Ошибка получения данных")
        items = items_resp.json()
        if not items:
            raise Exception("Нет данных по артикулу")

        product = items[0]
        return {
            "name": product.get("name"),
            "price": product.get("price"),
            "rating": product.get("rating"),
            "feedbacks": product.get("feedbacks"),
            "seller": product.get("sellerName") or product.get("seller")
        }
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Таймаут при запросе к Apify")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

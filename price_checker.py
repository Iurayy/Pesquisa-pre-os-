import os
import json
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import requests
from google import genai
from google.genai import types

app = FastAPI(title="Setup Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

class ItemRequirement(BaseModel):
    category: str
    target_spec: str

class FolderAnalysisRequest(BaseModel):
    folder_name: str
    total_budget: float
    items: List[ItemRequirement]
    notify_telegram: Optional[bool] = False

class SimilarItem(BaseModel):
    name: str
    price: float
    note: str
    specs: List[str] = []

class AnalyzedItem(BaseModel):
    category: str
    name: str
    price: float
    specs: List[str] = []
    similars: List[SimilarItem] = []

class AIAnalysisResponse(BaseModel):
    items: List[AnalyzedItem]
    summary_report: str

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def send_telegram_alert(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro Telegram: {e}")

@app.get("/")
def health_check():
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    return {
        "status": "online",
        "gemini_configured": has_key,
        "message": "Backend ativo"
    }

@app.post("/analyze")
def analyze_folder(data: FolderAnalysisRequest):
    client = get_gemini_client()
    if not client:
        raise HTTPException(
            status_code=500,
            detail="A variável GEMINI_API_KEY não foi encontrada nas Environment Variables do Render."
        )

    items_list_str = "\n".join([f"- {it.category}: {it.target_spec}" for it in data.items])

    prompt = f"""
Você é um consultor especialista em hardware, periféricos e compras no Brasil.
Projeto: {data.folder_name}
Orçamento Máximo: R$ {data.total_budget:.2f}

Itens solicitados:
{items_list_str}

Para cada item:
1. Informe o nome do produto principal recomendado no mercado brasileiro e seu preço estimado à vista (em R$).
2. Liste de 1 a 2 alternativas/similares na mesma categoria.
3. Inclua 3 especificações sucintas para cada um.
4. Faça uma análise no campo summary_report avaliando se os itens cabem nos R$ {data.total_budget:.2f}.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIAnalysisResponse,
            ),
        )

        parsed = json.loads(response.text)

        # Adiciona links diretos de busca de compras
        for it in parsed.get("items", []):
            q_main = urllib.parse.quote_plus(f"{it.get('category', '')} {it.get('name', '')}")
            it["store_url"] = f"https://www.google.com/search?tbm=shop&q={q_main}"
            for sim in it.get("similars", []):
                q_sim = urllib.parse.quote_plus(f"{it.get('category', '')} {sim.get('name', '')}")
                sim["store_url"] = f"https://www.google.com/search?tbm=shop&q={q_sim}"

        if data.notify_telegram:
            rep = parsed.get("summary_report", "")
            msg = f"📁 *{data.folder_name}* (Teto: R$ {data.total_budget:.2f})\n\n{rep}"
            send_telegram_alert(msg)

        return parsed

    except Exception as e:
        print(f"Erro na IA: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno da IA: {str(e)}")

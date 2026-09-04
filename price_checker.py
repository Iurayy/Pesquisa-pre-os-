import os
import json
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

def get_gemini_client():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return None
    return genai.Client(api_key=key)

class ItemRequirement(BaseModel):
    category: str
    target_spec: str

class FolderAnalysisRequest(BaseModel):
    folder_name: str
    total_budget: float
    items: List[ItemRequirement]
    notify_telegram: Optional[bool] = False

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
    return {
        "status": "online",
        "message": "Backend ativo e funcionando",
        "gemini_ready": bool(os.environ.get("GEMINI_API_KEY"))
    }

@app.post("/analyze")
def analyze_folder(data: FolderAnalysisRequest):
    client = get_gemini_client()
    if not client:
        raise HTTPException(
            status_code=500,
            detail="Chave GEMINI_API_KEY não localizada nas Environment Variables do Render."
        )

    items_list_str = "\n".join([f"- Categoria: {it.category} | Especificação: {it.target_spec}" for it in data.items])

    prompt = f"""
Você é um consultor especialista em tecnologia, hardware e compras no mercado brasileiro.
Projeto: {data.folder_name}
Orçamento limite: R$ {data.total_budget:.2f}

Itens solicitados:
{items_list_str}

Instruções:
1. Para cada item, indique o nome oficial recomendado no Brasil, o preço estimado à vista (numérico float em R$) e 3 especificações sucintas.
2. Forneça de 1 a 2 similares na MESMA categoria, com preço estimado e uma nota curta explicando o diferencial.
3. Elabore um parecer sobre o orçamento em 'summary_report'.

Gere EXCLUSIVAMENTE um JSON com esta estrutura:
{{
  "items": [
    {{
      "category": "Nome da Categoria",
      "name": "Nome do Produto",
      "price": 1000.0,
      "specs": ["Espec 1", "Espec 2", "Espec 3"],
      "similars": [
        {{
          "name": "Nome do Similar",
          "price": 950.0,
          "note": "ótimo custo-benefício",
          "specs": ["Destaque 1", "Destaque 2"]
        }}
      ]
    }}
  ],
  "summary_report": "Texto com o parecer e análise orçamentária."
}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        parsed = json.loads(response.text.strip())

        # Adiciona links dinâmicos de compra
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

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Erro de formatação JSON na resposta da IA.")
    except Exception as e:
        print(f"Erro na geração: {e}")
        raise HTTPException(status_code=500, detail=str(e))

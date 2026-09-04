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
        "message": "Backend ativo com links diretos de lojas",
        "gemini_ready": bool(os.environ.get("GEMINI_API_KEY"))
    }

@app.post("/analyze")
def analyze_folder(data: FolderAnalysisRequest):
    client = get_gemini_client()
    if not client:
        raise HTTPException(
            status_code=500,
            detail="Chave GEMINI_API_KEY não configurada no Render."
        )

    items_list_str = "\n".join([f"- Categoria: {it.category} | Especificação: {it.target_spec}" for it in data.items])

    prompt = f"""
Você é um consultor especialista em tecnologia, hardware e compras no Brasil.
Projeto: {data.folder_name}
Orçamento total limite: R$ {data.total_budget:.2f}

Itens solicitados:
{items_list_str}

Suas tarefas:
1. PESQUISE ofertas reais e ativas na web brasileira para os produtos solicitados (priorize lojas conhecidas como Kabum, Pichau, TerabyteShop, Amazon BR, Mercado Livre oficial).
2. Para cada item da lista:
   - Identifique o nome do produto exato disponível.
   - Forneça o PREÇO À VISTA REAL (em R$ float) praticado na loja encontrada.
   - Extraia a URL DIRETA da página do produto/anúncio daquela loja específica (ex: link direto da Kabum, Terabyte, Amazon, etc.). NUNCA use links genéricos de busca ou links de consoles.
   - Forneça 3 especificações técnicas objetivas.
3. Para cada item, encontre de 1 a 2 PRODUTOS SIMILARES/CONCORRENTES na MESMA categoria, também com:
   - Nome real do similar.
   - Preço à vista real no Brasil.
   - Link DIRETO para a página de compra/anúncio do similar.
   - Nota explicativa do custo-benefício.
4. Analise se o setup completo cabe no orçamento de R$ {data.total_budget:.2f} e gere o parecer no campo 'summary_report'.

IMPORTANTE: Responda ESTRITAMENTE em formato JSON válido, sem texto explicativo adicional, sem blocos markdown externos:
{{
  "items": [
    {{
      "category": "Categoria",
      "name": "Nome Real do Produto na Loja",
      "price": 1250.00,
      "store_name": "Kabum",
      "store_url": "https://www.kabum.com.br/produto/exemplo-direto",
      "specs": ["Espec 1", "Espec 2", "Espec 3"],
      "similars": [
        {{
          "name": "Nome Real do Similar",
          "price": 1100.00,
          "store_name": "TerabyteShop",
          "store_url": "https://www.terabyteshop.com.br/produto/exemplo-direto",
          "note": "mesmo desempenho, mais barato",
          "specs": ["Destaque 1", "Destaque 2"]
        }}
      ]
    }}
  ],
  "summary_report": "Parecer detalhado sobre o orçamento."
}}
"""

    try:
        # Usa busca na web ativa para encontrar os links reais de compra
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}]
            )
        )

        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("\n", 1)[0]
            raw_text = raw_text.strip()

        parsed = json.loads(raw_text)

        # Validação e fallback caso a IA deixe algum link vazio
        for it in parsed.get("items", []):
            if not it.get("store_url") or "google.com/search" in it.get("store_url", ""):
                q = urllib.parse.quote_plus(f"{it.get('name', '')} comprar brasil")
                it["store_url"] = f"https://www.google.com/search?q={q}"

            for sim in it.get("similars", []):
                if not sim.get("store_url") or "google.com/search" in sim.get("store_url", ""):
                    q_s = urllib.parse.quote_plus(f"{sim.get('name', '')} comprar brasil")
                    sim["store_url"] = f"https://www.google.com/search?q={q_s}"

        if data.notify_telegram:
            rep = parsed.get("summary_report", "")
            msg = f"📁 *{data.folder_name}* (Teto: R$ {data.total_budget:.2f})\n\n{rep}"
            send_telegram_alert(msg)

        return parsed

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="A IA não estruturou o JSON perfeitamente nesta busca. Clique em pesquisar novamente."
        )
    except Exception as e:
        print(f"Erro na pesquisa com links: {e}")
        raise HTTPException(status_code=500, detail=str(e))

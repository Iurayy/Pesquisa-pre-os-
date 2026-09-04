import os
import json
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
from google import genai

app = FastAPI(title="Setup Advisor API")

# Permite chamadas de qualquer origem (GitHub Pages, localhost, mobile)
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
    if not GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Erro ao inicializar cliente Gemini: {e}")
        return None

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
        print(f"Erro no envio Telegram: {e}")

@app.get("/")
def health_check():
    return {"status": "online", "message": "Backend ativo e funcionando"}

@app.post("/analyze")
def analyze_folder(data: FolderAnalysisRequest):
    client = get_gemini_client()
    if not client:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY não configurada ou inválida no Render."
        )

    items_list_str = "\n".join([f"- Categoria: {it.category} | Especificacao: {it.target_spec}" for it in data.items])

    prompt = f"""
Você é um consultor especialista em tecnologia, hardware e compras no mercado brasileiro.
Projeto: {data.folder_name}
Orçamento limite: R$ {data.total_budget:.2f}

Itens desejados pelo usuário:
{items_list_str}

Instruções obrigatórias:
1. Para cada item da lista, informe o nome oficial de mercado, um preço médio estimado à vista no Brasil (em R$) e 3 especificações técnicas objetivas.
2. Identifique de 1 a 2 alternativas/similares na MESMA categoria de uso e patamar de desempenho, também com preço estimado e especificações.
3. Analise se a soma dos itens principais cabe no orçamento de R$ {data.total_budget:.2f} e elabore um parecer no campo 'summary_report'.

Responda ESTRITAMENTE em formato JSON válido, sem texto explicativo antes ou depois, sem crases markdown (```json).
Estrutura exigida:
{{
  "items": [
    {{
      "category": "Nome da Categoria",
      "name": "Nome do Produto Principal",
      "price": 1000.0,
      "specs": ["Espec 1", "Espec 2", "Espec 3"],
      "similars": [
        {{
          "name": "Nome do Similar",
          "price": 950.0,
          "note": "ótimo custo benefício",
          "specs": ["Destaque 1", "Destaque 2"]
        }}
      ]
    }}
  ],
  "summary_report": "Texto do seu parecer sobre os preços e orçamento."
}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        raw_text = response.text.strip()

        # Limpeza defensiva de markdown
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("\n", 1)[0]
            raw_text = raw_text.strip()

        parsed = json.loads(raw_text)

        # Gera URLs de busca direta seguras para cada produto
        for it in parsed.get("items", []):
            q_main = urllib.parse.quote_plus(f"{it.get('category', '')} {it.get('name', '')}")
            it["store_url"] = f"[https://www.google.com/search?tbm=shop&q=](https://www.google.com/search?tbm=shop&q=){q_main}"
            for sim in it.get("similars", []):
                q_sim = urllib.parse.quote_plus(f"{it.get('category', '')} {sim.get('name', '')}")
                sim["store_url"] = f"[https://www.google.com/search?tbm=shop&q=](https://www.google.com/search?tbm=shop&q=){q_sim}"

        if data.notify_telegram:
            rep = parsed.get("summary_report", "")
            msg = f"📁 *{data.folder_name}* (Teto: R$ {data.total_budget:.2f})\n\n{rep}"
            send_telegram_alert(msg)

        return parsed

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, 
            detail="A IA não retornou um formato JSON válido. Tente novamente em instantes."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

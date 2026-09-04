import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from google import genai
import requests

app = FastAPI(title="Universal Price & Spec Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

class ItemRequirement(BaseModel):
    category: str
    target_spec: str

class FolderAnalysisRequest(BaseModel):
    folder_name: str
    total_budget: float
    items: List[ItemRequirement]
    notify_telegram: bool = False

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
        print(f"Erro ao enviar Telegram: {e}")

@app.get("/")
def health_check():
    return {"status": "online"}

@app.post("/analyze")
def analyze_folder(data: FolderAnalysisRequest):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY ausente no servidor.")

    items_text = "\n".join([f"- Categoria: {it.category} | Produto/Busca: {it.target_spec}" for it in data.items])

    prompt = f"""
    Você é um consultor especialista em compras, tecnologia e análise de mercado no Brasil.
    Projeto: {data.folder_name}
    Orçamento Máximo: R$ {data.total_budget:.2f}

    Itens solicitados:
    {items_text}

    Sua tarefa:
    1. Analise o produto solicitado em cada categoria. O usuário pode pedir qualquer produto (hardware, periféricos, áudio, eletrônicos, etc.).
    2. Estime o preço médio de mercado atual à vista em reais (BRL).
    3. Traga de 1 a 3 similares/concorrentes diretos EXATAMENTE dentro da mesma categoria de desempenho/função, com seus preços estimados e pontos fortes.
    4. Para cada item principal e similar, forneça uma URL de busca direta no Google Shopping ou loja recomendada no padrão:
       "https://www.google.com/search?tbm=shop&q=" + nome_codificado
    5. No campo 'specs', detalhe 3 a 5 especificações técnicas cruciais de forma resumida e direta.
    6. Forneça uma análise orçamentária geral em 'summary_report'.

    Retorne ESTRITAMENTE um JSON válido (sem texto antes ou depois, sem ```json):
    {{
      "items": [
        {{
          "category": "Nome da Categoria",
          "name": "Nome Oficial do Produto",
          "price": 1250.00,
          "store_url": "[https://www.google.com/search?tbm=shop&q=Nome+Do+Produto](https://www.google.com/search?tbm=shop&q=Nome+Do+Produto)",
          "specs": [
            "Especificação 1",
            "Especificação 2",
            "Especificação 3"
          ],
          "similars": [
            {{
              "name": "Nome do Similar 1",
              "price": 1100.00,
              "store_url": "[https://www.google.com/search?tbm=shop&q=Nome+Similar+1](https://www.google.com/search?tbm=shop&q=Nome+Similar+1)",
              "note": "mesmo desempenho, mais barato",
              "specs": ["Destaque técnico 1", "Destaque técnico 2"]
            }}
          ]
        }}
      ],
      "summary_report": "Resumo geral da consultoria, viabilidade do orçamento e recomendações."
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        raw_text = response.text.strip()
        if raw_text.startswith("

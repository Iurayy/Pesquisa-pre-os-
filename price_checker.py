import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types
import requests

app = FastAPI(title="PC Price Advisor API")

# Libera o acesso para testar de qualquer navegador/celular
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
    except Exception:
        pass

@app.get("/")
def health_check():
    return {"status": "online", "message": "API de Análise de Preços Ativa!"}

@app.post("/analyze")
def analyze_folder(data: FolderAnalysisRequest):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY não configurada no servidor.")

    items_text = "\n".join([f"- {it.category}: {it.target_spec}" for it in data.items])

    prompt = f"""
    Você é um especialista em hardware e orçamentos no Brasil.
    Projeto / Pasta: {data.folder_name}
    Orçamento Total Estipulado: R$ {data.total_budget:.2f}

    Componentes e especificações solicitadas:
    {items_text}

    Sua tarefa:
    1. Pesquise no mercado brasileiro (Kabum, Pichau, Terabyte, Amazon BR) os preços médios/menores preços atuais à vista para essas peças ou similares no mesmo patamar de desempenho.
    2. Identifique se há alternativas similares mais baratas ou de melhor custo-benefício.
    3. Calcule se a soma total das peças cabe no teto de R$ {data.total_budget:.2f}.
    4. Veredito:
       - Diga se vale a pena fechar a compra agora.
       - Se alguma peça estiver cara a ponto de comprometer o resto do orçamento, aponte exatamente qual e dê alternativas.
    5. Formate a resposta de forma limpa, direta, com emojis e tópicos legíveis em telas pequenas.
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}]
            )
        )
        report = response.text.strip()

        if data.notify_telegram:
            msg = f"📁 *Pasta:* {data.folder_name}\n💰 *Orçamento:* R$ {data.total_budget:.2f}\n\n{report}"
            send_telegram_alert(msg)

        return {
            "folder": data.folder_name,
            "budget": data.total_budget,
            "analysis": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

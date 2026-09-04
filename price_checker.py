import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from google import genai
import requests

app = FastAPI(title="PC Price Advisor API")

# Libera o acesso para navegadores no celular e computador
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
        print(f"Erro ao enviar para o Telegram: {e}")

@app.get("/")
def health_check():
    return {"status": "online", "message": "API de Análise de Preços Ativa!"}

@app.post("/analyze")
def analyze_folder(data: FolderAnalysisRequest):
    if not client:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY não configurada no servidor.")

    items_text = "\n".join([f"- {it.category}: {it.target_spec}" for it in data.items])

    prompt = f"""
    Você é um consultor especialista em montagem de computadores, hardware e orçamentos no Brasil.
    Projeto / Pasta: {data.folder_name}
    Orçamento Total Estipulado: R$ {data.total_budget:.2f}

    Componentes e especificações solicitadas:
    {items_text}

    Sua tarefa de consultoria:
    1. Avalie as peças solicitadas e indique a faixa de preço médio atual dessas categorias no mercado brasileiro (Kabum, Pichau, Terabyte, Amazon).
    2. Sugira peças similares/equivalentes no mesmo patamar de desempenho que ofereçam melhor custo-benefício, se aplicável.
    3. Analise o impacto financeiro global:
       - Some a estimativa das peças e diga com clareza se o setup completo fecha dentro do limite de R$ {data.total_budget:.2f}.
       - Caso o orçamento esteja apertado ou estourando, aponte exatamente qual componente está pesando demais e recomende onde economizar sem perder performance essencial.
    4. Dê um veredito final claro: 'Vale a pena comprar agora' ou 'Ajuste os itens X e Y para caber no orçamento'.
    5. Formate a resposta de forma limpa, direta, com emojis e tópicos curtos para leitura rápida no celular e Telegram.
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
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

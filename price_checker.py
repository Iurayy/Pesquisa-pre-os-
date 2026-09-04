import os
import json
import requests
from google import genai
from google.genai import types

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=15)

def evaluate_build():
    with open("products.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    budget = config.get("total_budget", 6000.00)
    items = config.get("hardware_requirements", [])

    prompt = f"""
    Você é um assistente sênior de hardware e consultor de compras no mercado brasileiro.
    O usuário possui um orçamento TOTAL rigoroso de R$ {budget:.2f} para montar o setup completo.

    Lista de componentes desejados (ou alternativas com o mesmo nível de desempenho/qualidade):
    {json.dumps(items, indent=2, ensure_ascii=False)}

    Sua tarefa:
    1. Pesquise na internet os preços atuais médios/à vista no Brasil (Kabum, Pichau, Terabyte, Amazon BR, etc.) para os itens ou similares equivalentes.
    2. Encontre se há promoções de destaque ou peças similares mais baratas que entregam a mesma performance.
    3. Analise o impacto financeiro global:
       - Se encontrar uma peça específica barata (ou similar vantajosa), analise: comprá-la agora deixará saldo suficiente para comprar as outras peças restantes sem estourar os R$ {budget:.2f}?
       - Exemplo de alerta se for inviável: 'A GPU X está por R$ 3.400. Apesar do preço aceitável, sobrariam apenas R$ 2.600 para as outras 8 peças, tornando inviável fechar com Ryzen 5 7600 e DDR5 dentro de R$ {budget:.2f}.'
       - Exemplo se for viável: 'Vale a pena comprar a RAM/GPU agora por R$ Y, pois os outros componentes somam R$ Z e fecham dentro dos R$ {budget:.2f}!'
    4. Seja direto e prático: cite o componente encontrado (ou similar recomendado), o preço aproximado à vista e a recomendação final de compra.
    5. Formate a mensagem de maneira limpa com marcadores e emojis para leitura rápida no Telegram.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}]
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"Erro ao processar análise: {e}")
        return None

def main():
    report = evaluate_build()
    if report:
        header = "🖥️ *Relatório & Consultoria de Preços*\n\n"
        send_telegram_alert(header + report)

if __name__ == "__main__":
    main()

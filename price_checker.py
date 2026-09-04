import os
import re
import json
import requests
from bs4 import BeautifulSoup
from google import genai

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload, timeout=10)

def extract_price(html_text):
    prompt = (
        "Identifique o preço à vista ou atual do produto neste texto. "
        "Retorne APENAS o número decimal (ex: 1250.00). "
        "Sem texto, sem moeda. Se não encontrar, retorne 'null'.\n\n"
        f"{html_text[:3500]}"
    )
    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        clean = re.sub(r"[^\d.]", "", res.text.strip())
        return float(clean) if clean else None
    except Exception:
        return None

def analyze_budget_and_deals(budget, collected_data):
    prompt = f"""
    Você é um consultor especialista em hardware e montagem de PC.
    O usuário tem um orçamento total estipulado de R$ {budget:.2f}.
    
    Aqui está a lista de componentes, seus preços-alvo e o preço atual detectado nas lojas:
    {json.dumps(collected_data, indent=2, ensure_ascii=False)}
    
    Regras da sua análise:
    1. Se algum componente bateu o 'target_price' (está barato), verifique se vale a pena comprar agora.
    2. Calcule o impacto no orçamento total: se ele pagar o preço atual desta peça, o dinheiro que sobra é suficiente para pagar os alvos dos outros componentes?
    3. Se não for suficiente, alerte explicitamente: 'Se você comprar X agora por R$ Y, vai estourar o orçamento e faltará dinheiro para [Componentes Z]'.
    4. Se o preço estiver excelente e não comprometer o teto de R$ {budget:.2f}, encoraje a compra com: 'Vale a pena comprar agora!'.
    5. Seja ultra direto, use tópicos curtos e emojis. Limite o texto a 180 palavras para leitura rápida no Telegram.
    
    Caso nenhum produto esteja em promoção vantajosa ou viável no momento, responda apenas: NO_ACTION
    """
    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return res.text.strip()
    except Exception as e:
        print(f"Erro na análise de IA: {e}")
        return "NO_ACTION"

def main():
    with open("products.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    budget = config.get("total_budget", 6000.00)
    items = config.get("items", [])

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9"
    }

    collected = []
    has_target_hit = False

    for item in items:
        price = None
        try:
            r = requests.get(item["url"], headers=headers, timeout=12)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                price = extract_price(soup.get_text(separator=" ", strip=True))
        except Exception:
            pass

        collected.append({
            "name": item["name"],
            "url": item["url"],
            "target_price": item["target_price"],
            "current_price": price
        })

        if price and price <= item["target_price"]:
            has_target_hit = True

    # Só gasta tokens e envia mensagem se ao menos uma peça estiver em preço atrativo
    if has_target_hit:
        advice = analyze_budget_and_deals(budget, collected)
        if advice != "NO_ACTION":
            send_telegram_alert(f"💡 *Consultoria de Setup & Alerta de Preço*\n\n{advice}")

if __name__ == "__main__":
    main()

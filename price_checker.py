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

def extract_price_with_gemini(html_snippet):
    prompt = (
        "Analise o texto a seguir e identifique o preço atual do produto principal/à vista. "
        "Retorne APENAS o número com ponto decimal (ex: 149.90 ou 1250.00). "
        "Não inclua R$, moedas ou texto explicativo. Se não achar, retorne 'null'.\n\n"
        f"Texto:\n{html_snippet}"
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        val = response.text.strip()
        clean_val = re.sub(r"[^\d.]", "", val)
        return float(clean_val) if clean_val else None
    except Exception:
        return None

def check_prices():
    with open("products.json", "r", encoding="utf-8") as f:
        products = json.load(f)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    for prod in products:
        try:
            res = requests.get(prod["url"], headers=headers, timeout=15)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()

            text_sample = soup.get_text(separator=" ", strip=True)[:4000]
            current_price = extract_price_with_gemini(text_sample)

            if current_price and current_price <= prod["target_price"]:
                msg = (
                    f"🚨 *Alerta de Preço Baixo!*\n\n"
                    f"*{prod['name']}*\n"
                    f"💰 Preço Atual: *R$ {current_price:.2f}*\n"
                    f"🎯 Seu Alvo: R$ {prod['target_price']:.2f}\n\n"
                    f"[Acessar Produto]({prod['url']})"
                )
                send_telegram_alert(msg)

        except Exception as e:
            print(f"Erro ao verificar {prod['name']}: {e}")

if __name__ == "__main__":
    check_prices()

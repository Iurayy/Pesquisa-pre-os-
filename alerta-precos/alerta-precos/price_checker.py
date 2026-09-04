"""
Verificador de preços com alerta via Telegram.

Fluxo:
1. Lê a lista de produtos em products.json
2. Para cada produto, baixa a página e tenta extrair o preço (meta tags /
   JSON-LD comuns em lojas). Se não conseguir, usa a IA (Gemini, gratuito)
   como plano B para ler o preço a partir do texto da página.
3. Compara com o último preço salvo em price_history.json e com o
   target_price definido pelo usuário.
4. Se o preço caiu OU bateu o alvo, envia uma mensagem no Telegram.
5. Atualiza price_history.json (o workflow do GitHub Actions faz o commit).
"""

import json
import os
import re
import sys
import time

import requests

PRODUCTS_FILE = "products.json"
HISTORY_FILE = "price_history.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

PRICE_REGEXES = [
    r'"price"\s*:\s*"?([\d]+\.?[\d]*)"?',                 # JSON-LD schema.org
    r'itemprop="price"\s+content="([\d]+\.?[\d]*)"',      # meta itemprop
    r'property="product:price:amount"\s+content="([\d]+\.?[\d]*)"',  # og:price
]


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_price_with_regex(html: str):
    for pattern in PRICE_REGEXES:
        match = re.search(pattern, html)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def extract_price_with_ai(html: str, product_name: str):
    """Plano B: pede pro Gemini (gratuito) achar o preço no HTML bruto."""
    if not GEMINI_API_KEY:
        return None

    # Reduz o HTML para não estourar o limite de tokens
    trimmed = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL)
    trimmed = re.sub(r"<style.*?</style>", "", trimmed, flags=re.DOTALL)
    trimmed = trimmed[:15000]

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = (
        f"Este é o HTML de uma página de produto chamado '{product_name}'. "
        "Encontre o preço de venda atual do produto e responda APENAS com "
        "o número (use ponto como separador decimal, sem símbolo de moeda, "
        "sem texto extra). Se não encontrar, responda apenas: NENHUM.\n\n"
        f"HTML:\n{trimmed}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        resp = requests.post(url, json=body, timeout=30)
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
        return float(cleaned) if cleaned and cleaned != "." else None
    except Exception as e:
        print(f"  [IA] Falha ao extrair preço via IA: {e}")
        return None


def get_current_price(url: str, product_name: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Erro ao baixar página: {e}")
        return None

    price = extract_price_with_regex(resp.text)
    if price is None:
        print("  Regex não achou o preço, tentando com IA...")
        price = extract_price_with_ai(resp.text, product_name)
    return price


def send_telegram_message(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram não configurado (faltam secrets). Mensagem:", text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        print(f"Erro ao enviar mensagem no Telegram: {e}")


def main():
    products = load_json(PRODUCTS_FILE, [])
    history = load_json(HISTORY_FILE, {})

    if not products:
        print("Nenhum produto cadastrado em products.json.")
        return

    for product in products:
        name = product.get("name", "Produto sem nome")
        url = product.get("url", "")
        target_price = product.get("target_price")

        print(f"Verificando: {name}")

        if not url or "COLOQUE-O-LINK" in url:
            print("  Link ainda não configurado, pulando.")
            continue

        current_price = get_current_price(url, name)
        if current_price is None:
            print("  Não foi possível obter o preço agora.")
            continue

        print(f"  Preço atual: R$ {current_price:.2f}")

        last_price = history.get(url, {}).get("last_price")

        alert_reasons = []
        if last_price is not None and current_price < last_price:
            queda = last_price - current_price
            alert_reasons.append(
                f"📉 Caiu R$ {queda:.2f} (de R$ {last_price:.2f} para R$ {current_price:.2f})"
            )
        if target_price is not None and current_price <= target_price:
            alert_reasons.append(
                f"🎯 Atingiu seu preço-alvo de R$ {target_price:.2f}"
            )

        if alert_reasons:
            message = (
                f"<b>{name}</b>\n"
                f"Preço atual: R$ {current_price:.2f}\n"
                + "\n".join(alert_reasons)
                + f"\n{url}"
            )
            send_telegram_message(message)
            print("  Alerta enviado!")

        history[url] = {"last_price": current_price, "checked_at": int(time.time())}

    save_json(HISTORY_FILE, history)
    print("Verificação concluída.")


if __name__ == "__main__":
    main()

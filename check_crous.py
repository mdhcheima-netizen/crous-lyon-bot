#!/usr/bin/env python3
"""
Vérifie UNIQUEMENT les logements INDIVIDUELS (pas de colocation) dans une
liste précise de résidences CROUS à Lyon (phase complémentaire 2026-2027),
et envoie une notification Telegram pour chaque NOUVELLE annonce détectée,
en indiquant le rang de préférence de la résidence.

Le site cible étant une application JavaScript (SPA), on utilise Playwright
(un navigateur Chromium piloté automatiquement) pour charger les pages
exactement comme le ferait une personne, plutôt qu'une simple requête HTTP.
"""

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://trouverunlogement.lescrous.fr"
SEARCH_URL = f"{BASE_URL}/tools/45/search"  # 45 = année universitaire 2026-2027
DATA_FILE = Path(__file__).parent / "data" / "seen.json"

RESIDENCES = [
    {"rank": 1, "label": "RESIDENCE BUGEAUD", "match": "BUGEAUD",
     "address": "119 Rue Bugeaud 69006 Lyon"},
    {"rank": 2, "label": "RESIDENCE LIRONDELLE - CHATEAU DE LA BUIRE", "match": "LIRONDELLE",
     "address": "6 rue Rachais 69003 Lyon"},
    {"rank": 3, "label": "RESIDENCE GEORGES RINCK", "match": "RINCK",
     "address": "Lyon"},
    {"rank": 4, "label": "RESIDENCE LES QUAIS", "match": "LES QUAIS",
     "address": "96 rue Pasteur 69007 Lyon"},
    {"rank": 5, "label": "RESIDENCE VOLTAIRE", "match": "VOLTAIRE",
     "address": "67 rue Voltaire 69003 Lyon"},
    {"rank": 6, "label": "RESIDENCE JACQUES CAVALIER", "match": "CAVALIER",
     "address": "8 Rue J Koehler 69424 Lyon Cedex 03"},
    {"rank": 7, "label": "RESIDENCE PAUL BERT", "match": "PAUL BERT",
     "address": "8 rue Moissonnier 69003 Lyon"},
    {"rank": 8, "label": "RESIDENCE ALLIX", "match": "ALLIX",
     "address": "2 rue soeur Bouvier 69322 Lyon Cedex 05"},
]

COLOC_EXCLUDE = re.compile(r"colocation|coloc\b", re.IGNORECASE)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.upper()


def match_residence(card_text: str):
    norm = normalize(card_text)
    for res in RESIDENCES:
        if normalize(res["match"]) in norm:
            return res
    return None


def extract_listings(soup: BeautifulSoup) -> dict:
    results = {}
    for link in soup.select('a[href*="/accommodations/"]'):
        href = link.get("href", "")
        m = re.search(r"/accommodations/(\d+)", href)
        if not m:
            continue
        listing_id = m.group(1)

        card = link.find_parent("li") or link.find_parent("article") or link.parent
        card_text = card.get_text(" ", strip=True) if card else link.get_text(" ", strip=True)

        if COLOC_EXCLUDE.search(card_text):
            continue

        residence = match_residence(card_text)
        if residence is None:
            continue

        name = link.get_text(strip=True)
        full_url = href if href.startswith("http") else BASE_URL + href

        price_match = re.search(r"(\d{2,4}(?:,\d{2})?\s*€(?:.{0,20}€)?)", card_text)
        price = price_match.group(1) if price_match else "?"

        results[listing_id] = {
            "name": name,
            "url": full_url,
            "price": price,
            "residence_label": residence["label"],
            "residence_rank": residence["rank"],
            "text": card_text[:300],
        }
    return results


def get_total_pages(soup: BeautifulSoup) -> int:
    max_page = 1
    for a in soup.select('a[href*="page="]'):
        m = re.search(r"page=(\d+)", a.get("href", ""))
        if m:
            max_page = max(max_page, int(m.group(1)))
    title_text = soup.title.get_text() if soup.title else ""
    m2 = re.search(r"sur\s+(\d+)", title_text)
    if m2:
        max_page = max(max_page, int(m2.group(1)))
    return max_page


def fetch_all_target_listings() -> dict:
    all_results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="fr-FR",
        )
        page = context.new_page()

        print(f"Chargement de {SEARCH_URL} ...")
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1500)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        total_pages = get_total_pages(soup)
        print(f"Total pages à parcourir : {total_pages}")
        all_results.update(extract_listings(soup))

        for page_num in range(2, total_pages + 1):
            try:
                page.goto(
                    f"{SEARCH_URL}?page={page_num}",
                    wait_until="networkidle",
                    timeout=45000,
                )
                page.wait_for_timeout(800)
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                all_results.update(extract_listings(soup))
            except Exception as e:
                print(f"Erreur page {page_num}: {e}", file=sys.stderr)
                continue

        browser.close()

    return all_results


def load_seen() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}


def save_seen(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def send_telegram(message: str):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    if not resp.ok:
        print(f"Erreur envoi Telegram: {resp.status_code} {resp.text}", file=sys.stderr)


def main():
    current = fetch_all_target_listings()
    previous = load_seen()

    new_ids = [lid for lid in current if lid not in previous]

    print(f"{len(current)} logements ciblés trouvés, dont {len(new_ids)} nouveaux.")

    new_ids.sort(key=lambda lid: current[lid]["residence_rank"])

    if new_ids:
        for lid in new_ids:
            info = current[lid]
            msg = (
                f"🏠 <b>Logement individuel dispo !</b> (préférence n°{info['residence_rank']})\n\n"
                f"<b>{info['residence_label']}</b>\n"
                f"{info['name']}\n"
                f"💶 {info['price']}\n"
                f"🔗 {info['url']}"
            )
            send_telegram(msg)
            time.sleep(1)
    else:
        print("Aucun nouveau logement cette fois-ci parmi les résidences ciblées.")

    save_seen(current)


if __name__ == "__main__":
    main()

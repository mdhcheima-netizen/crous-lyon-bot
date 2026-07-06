#!/usr/bin/env python3
"""
Vérifie UNIQUEMENT les logements INDIVIDUELS (pas de colocation) dans une
liste précise de résidences CROUS à Lyon (phase complémentaire 2026-2027),
et envoie une notification Telegram pour chaque NOUVELLE annonce détectée,
en indiquant le rang de préférence de la résidence.
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

BASE_URL = "https://trouverunlogement.lescrous.fr"
SEARCH_URL = f"{BASE_URL}/tools/45/search"  # 45 = année universitaire 2026-2027
DATA_FILE = Path(__file__).parent / "data" / "seen.json"

# Résidences ciblées, dans l'ordre de préférence (1 = préférée)
# "match" = mot-clé unique qui permet de reconnaître la résidence dans le texte de l'annonce
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

# Mots qui indiquent une colocation -> à exclure systématiquement
COLOC_EXCLUDE = re.compile(r"colocation|coloc\b", re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CrousLyonWatcher/1.0; personal use)"
}


def normalize(text: str) -> str:
    """Enlève les accents et met en majuscule, pour matcher plus facilement."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.upper()


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_total_pages(soup: BeautifulSoup) -> int:
    max_page = 1
    for a in soup.select('a[href*="page="]'):
        m = re.search(r"page=(\d+)", a.get("href", ""))
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page


def match_residence(card_text: str):
    """Retourne le dict de la résidence ciblée si le texte de l'annonce correspond, sinon None."""
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

        # 1. On exclut toute colocation, quelle que soit la résidence
        if COLOC_EXCLUDE.search(card_text):
            continue

        # 2. On ne garde que les résidences ciblées
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


def fetch_all_target_listings() -> dict:
    all_results = {}
    soup = get_soup(SEARCH_URL)
    total_pages = get_total_pages(soup)
    all_results.update(extract_listings(soup))

    print(f"Total pages à parcourir : {total_pages}")

    for page in range(2, total_pages + 1):
        time.sleep(0.5)
        try:
            page_soup = get_soup(f"{SEARCH_URL}?page={page}")
        except requests.RequestException as e:
            print(f"Erreur page {page}: {e}", file=sys.stderr)
            continue
        all_results.update(extract_listings(page_soup))

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

    # On trie les nouveaux par ordre de préférence (rang 1 = message envoyé en premier)
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

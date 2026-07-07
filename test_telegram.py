#!/usr/bin/env python3
"""Envoie un simple message de test pour vérifier que Telegram est bien configuré."""

import os
import sys

import requests


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        print("ERREUR : la variable TELEGRAM_BOT_TOKEN est vide ou absente.", file=sys.stderr)
        sys.exit(1)
    if not chat_id:
        print("ERREUR : la variable TELEGRAM_CHAT_ID est vide ou absente.", file=sys.stderr)
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": "👋 Bonjour ! Le bot CROUS Lyon est bien configuré et peut t'envoyer des messages.",
        },
        timeout=15,
    )

    print(f"Code de réponse HTTP : {resp.status_code}")
    print(f"Réponse de Telegram : {resp.text}")

    if not resp.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

Commit changes

2. Créer le workflow de test

"Add file" → "Create new file"
Nom du fichier : .github/workflows/test_telegram.yml
Colle ce contenu :

yamlname: Test connexion Telegram

on:
  workflow_dispatch: {}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Récupérer le code
        uses: actions/checkout@v4

      - name: Installer Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Installer les dépendances
        run: pip install requests

      - name: Envoyer le message de test
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python test_telegram.py

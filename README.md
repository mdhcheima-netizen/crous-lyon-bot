# Bot de veille logements CROUS Lyon

Vérifie automatiquement, toutes les heures, les logements CROUS **individuels
uniquement** (aucune colocation) disponibles dans une liste précise de
résidences à Lyon pour 2026-2027, et t'envoie un message Telegram pour
chaque nouvelle annonce, avec ton rang de préférence.

## Résidences surveillées (par ordre de préférence)
1. Résidence Bugeaud — 119 Rue Bugeaud, 69006 Lyon
2. Résidence Lirondelle - Château de la Buire — 6 rue Rachais, 69003 Lyon
3. Résidence Georges Rinck — Lyon
4. Résidence Les Quais — 96 rue Pasteur, 69007 Lyon
5. Résidence Voltaire — 67 rue Voltaire, 69003 Lyon
6. Résidence Jacques Cavalier — 8 Rue J Koehler, 69424 Lyon Cedex 03
7. Résidence Paul Bert — 8 rue Moissonnier, 69003 Lyon
8. Résidence Allix — 2 rue soeur Bouvier, 69322 Lyon Cedex 05

Pour changer cette liste ou l'ordre, modifie la liste `RESIDENCES` en haut
du fichier `check_crous.py`.

## Mise en place (5-10 minutes, à faire une seule fois)

### 1. Créer le dépôt sur GitHub
1. Va sur https://github.com/new
2. Nom du dépôt : `crous-lyon-bot` (ou ce que tu veux)
3. Mets-le en **Private** (recommandé, même si le code ne contient aucun secret)
4. Clique "Create repository"

### 2. Envoyer ces fichiers dans le dépôt
Sur la page de ton nouveau dépôt vide, clique sur "uploading an existing file"
et glisse-dépose TOUS les fichiers et dossiers de ce projet en conservant la
structure exacte :
```
crous-lyon-bot/
├── .github/workflows/check.yml
├── check_crous.py
├── data/seen.json
└── README.md
```
⚠️ Le dossier `.github` doit vraiment s'appeler comme ça (avec le point).

### 3. Ajouter tes identifiants Telegram en secret (jamais dans le code)
1. Dans ton dépôt GitHub : onglet **Settings** → **Secrets and variables** →
   **Actions**
2. Clique "New repository secret"
   - Nom : `TELEGRAM_BOT_TOKEN` → Valeur : ton token BotFather
3. Refais pareil pour :
   - Nom : `TELEGRAM_CHAT_ID` → Valeur : ton chat_id

### 4. Activer les Actions
1. Onglet **Actions** de ton dépôt
2. S'il te demande de confirmer l'activation des workflows, clique dessus
3. Tu verras "Vérification logements CROUS Lyon" dans la liste
4. Clique dessus → bouton **"Run workflow"** pour lancer un premier test
   manuel tout de suite (ne pas attendre l'heure pile)

### 5. Vérifier que ça marche
- Va dans l'onglet Actions, clique sur l'exécution en cours, regarde les logs
- Si tout est vert ✅, tu devrais recevoir un message Telegram si des
  logements Lyon existent déjà (normal lors du tout premier lancement,
  ce sont les annonces "déjà là" qui sont considérées comme la base de départ)
- À partir de la 2e exécution, tu ne recevras un message QUE pour les
  nouvelles annonces qui apparaissent

## Ensuite ?
Le bot tourne tout seul, gratuitement, toutes les heures, même téléphone
éteint. Tu peux fermer GitHub et Telegram, tu recevras juste les
notifications quand il y a du nouveau.

## Modifier la fréquence
Dans `.github/workflows/check.yml`, la ligne :
```
- cron: "0 * * * *"
```
`"0 * * * *"` = toutes les heures pile. Pour toutes les 30 min :
`"*/30 * * * *"`. GitHub Actions gratuit permet largement cette fréquence
pour un usage personnel.

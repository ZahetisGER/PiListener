#!/bin/bash
# ============================================================
# PiListener → GitHub Push Script
# Führt: Bob aus, nachdem das Projekt fertig ist.
#
# Nutzung:
#   GITHUB_TOKEN=<dein-token> ./push-github.sh
#
# Oder vorher: gh auth login --with-token < <(echo <token>)
# ============================================================

set -e

REPO_NAME="PiListener"
GITHUB_USER="ZahetisGER"
DESCRIPTION="AI-powered audio listener that generates images from heard sounds"

# ---- Auth Check ----
if ! gh auth status &>/dev/null; then
    echo "❌ gh CLI nicht authentifiziert."
    echo "   Führe zuerst aus:"
    echo "   gh auth login"
    echo ""
    echo "   Oder setze GITHUB_TOKEN als Umgebungsvariable:"
    echo "   GITHUB_TOKEN=<token> ./push-github.sh"
    exit 1
fi

cd ~/PiListener

# ---- Remote prüfen / setzen ----
if git remote get-url origin &>/dev/null; then
    echo "ℹ️  Remote 'origin' existiert bereits: $(git remote get-url origin)"
else
    echo "📦 Repo auf GitHub anlegen..."
    gh repo create "$REPO_NAME" \
        --private \
        --description "$DESCRIPTION" \
        --source=. \
        --remote
fi

# ---- Branch & Commit ----
CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    git checkout -b main 2>/dev/null || git checkout -b master
fi

echo "📁 Commits erstellen..."
git add -A

if git diff --cached --quiet; then
    echo "ℹ️  Keine Änderungen zu committen."
else
    git commit -m "feat: initial PiListener implementation

- Audio listener (15min interval, 20s capture)
- STT via OpenRouter/NVIDIA free models
- AI image generation with metadata
- X11 fullscreen display with title bar
- Configurable via .env"
    echo "✅ Commit erstellt."
fi

# ---- Push ----
echo "🚀 Auf GitHub pushen..."
git push -u origin HEAD --force

echo ""
echo "✅ PiListener ist jetzt auf GitHub live:"
echo "   https://github.com/$GITHUB_USER/$REPO_NAME"

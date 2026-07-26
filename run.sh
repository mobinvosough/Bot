#!/bin/bash
set -e

echo "=========================================="
echo "          MIT SOURCE - ContentForwardBot  "
echo "=========================================="
echo ""

REPO="https://github.com/mobinvosough/Bot.git"
DIR="$HOME/Bot"

if [ -d "$DIR" ]; then
    echo "Updating repo..."
    cd "$DIR" && git pull
else
    echo "Cloning repo..."
    git clone "$REPO" "$DIR"
    cd "$DIR"
fi

if ! command -v python3 &>/dev/null; then
    echo "Installing Python3..."
    sudo apt update && sudo apt install -y python3 python3-venv python3-pip
fi

echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt tgcrypto

if [ ! -f ".env" ]; then
    echo ""
    echo "=== First-time setup ==="
    echo "Enter your bot credentials:"
    read -rp "BOT_TOKEN: " BOT_TOKEN
    read -rp "API_ID: " API_ID
    read -rp "API_HASH: " API_HASH
    read -rp "PHONE_NUMBER (e.g. +1234567890): " PHONE_NUMBER
    read -rp "ADMIN_IDS (comma separated): " ADMIN_IDS

    cat > .env <<EOF
BOT_TOKEN=$BOT_TOKEN
API_ID=$API_ID
API_HASH=$API_HASH
PHONE_NUMBER=$PHONE_NUMBER
ADMIN_IDS=$ADMIN_IDS
EOF
    echo ".env created."
fi

if [ ! -f "content_forward_bot.session" ]; then
    echo ""
    echo "Login to Pyrogram (enter the code sent to your Telegram):"
    python3 login.py
fi

echo ""
echo "Starting bot..."
python3 main.py

#!/bin/bash
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 پیدا نشد. ابتدا Python 3 را نصب کن."
  read -r -p "Enter برای خروج..."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[1/3] ساخت محیط Python..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
mkdir -p data

echo "[2/3] اجرای داشبورد..."
(sleep 2; open "http://127.0.0.1:5050") &
echo "[3/3] مرورگر باز می‌شود. برای بستن سرور Control+C بزن."
python app.py

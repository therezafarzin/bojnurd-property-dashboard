# Bojnurd Property Dashboard

Local Flask dashboard for collecting and analysing apartment-for-sale listings in Bojnurd. It stores market history locally in SQLite and presents neighbourhood-level price statistics.

## Stack

- Python 3
- Flask
- SQLite
- Requests and python-dotenv

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5050`.

Alternatively, on macOS run `start.command` from Finder.

## Data and privacy

The `data/` directory contains local market data and is intentionally excluded from Git. Create a local `.env` from `.env.example` when configuration is required; never commit real credentials or collected data.

## Status

Personal, local-use project under active maintenance.

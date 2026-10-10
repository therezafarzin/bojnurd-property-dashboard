# Development notes

- Run locally with `source .venv/bin/activate && python app.py`.
- Run tests with `python -m unittest tests/test_core.py` when changing Python logic.
- `data/` contains local collected market data; do not read, commit, move, or delete it unless the owner explicitly requests it.
- Keep configuration in `.env` locally and document non-sensitive variables in `.env.example`.

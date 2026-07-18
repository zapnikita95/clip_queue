# Local run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m backend.app
```

Health: `curl http://127.0.0.1:8765/health`
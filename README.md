# Agentic Dietician

## Run as CLI
```powershell
cd C:\Users\srv\AgenticDietician
.\venv\Scripts\python.exe agentic_main.py
```

## Run as API service (for UI)
```powershell
cd C:\Users\srv\AgenticDietician
.\venv\Scripts\python.exe api_server.py
```
API docs: http://localhost:8000/docs

## Run UI
```powershell
cd C:\Users\srv\AgenticDietician\ui
npm install
npm run dev
```
Open http://localhost:5173 — login with `1` or `2` (or `P-001` / `P-002`).

## Architecture
- `orchestrator_core.py` — shared 6-agent orchestrator
- `agentic_main.py` — CLI entry
- `api_server.py` — FastAPI on port 8000
- `ui/` — React chat UI

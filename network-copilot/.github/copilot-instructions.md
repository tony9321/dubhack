# Network Copilot: AI Agent Instructions

## Big Picture Architecture
- **Pipeline:**
  - `metrics_collector.py`: Collects network stats (ping, throughput) into SQLite (`data.db`).
  - `analyzer.py`: Detects anomalies and computes baselines from metrics.
  - `llm_wrapper.py`: Uses Gemini AI (if available) for natural language diagnosis; falls back to rule-based logic.
  - `app.py`: Flask web server for UI and API endpoints.
- **Data Flow:** Metrics → Analysis → Diagnosis → Web/API.

## Developer Workflows
- **Install:** `pip install -r requirements.txt`
- **Run:** `python app.py` (Flask UI at `http://localhost:5000`)
- **API:**
  - `GET /api/metrics`: Current metrics (JSON)
  - `GET /api/diagnosis`: AI diagnosis (JSON)
- **Config:** Copy `.env.example` to `.env` and set `GEMINI_API_KEY` (optional).
- **Testing:** Works on any Linux/Mac/Windows system with network connectivity. Uses real `ping`.

## Project-Specific Patterns
- **SQLite:** WAL mode enabled; `_db_lock` for thread safety in writes.
- **Metrics:**
  - Latency spike: >30% above baseline
  - Packet loss warning: >2%
  - Throughput drop: >20%
- **AI Integration:**
  - Gemini API via `google.generativeai` (optional)
  - Prompt: 2-3 sentence actionable network health summary
  - Fallback: Rule-based summary if no API key
- **Device Discovery:**
  - `device_discovery.py` for local network scan and per-device metrics

## Integration Points
- **External:**
  - Gemini AI API (optional)
  - Flask
  - SQLite
- **Hardware:**
  - Designed for Raspberry Pi, but portable
  - Uses system `ping` and `/proc/net/dev` for metrics

## Key Files/Directories
- `metrics_collector.py`, `analyzer.py`, `llm_wrapper.py`, `app.py`, `device_discovery.py`
- `templates/index.html`: Flask UI dashboard
- `requirements.txt`: Python dependencies
- `.env.example`: Environment variable template

---
For more details, see `README.md`. Please suggest improvements or request clarification for any section that is unclear or incomplete.
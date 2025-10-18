# Network Copilot - AI-Powered 5G Network Health Monitor

A Raspberry Pi-based network monitoring system that uses AI to diagnose and explain network health issues in real-time.

## 🎯 Overview

Network Copilot continuously monitors your 5G Home Internet connection and uses LLMs to provide natural-language explanations of network behavior. Instead of just seeing latency numbers, you get insights like:

> "Your upload is saturated. Pause cloud backups or wait 10 minutes. Current latency is 120ms (normally 40ms)."

**Ready for production on Raspberry Pi!** See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for Pi setup instructions.

## 🏗️ Architecture

```
metrics_collector.py  → Ping + Network stats → SQLite DB
         ↓
    analyzer.py       → Detects anomalies → JSON
         ↓
   llm_wrapper.py     → Calls OpenAI API → Natural Language Diagnosis
         ↓
      app.py          → Flask Web UI
```

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Gemini API Key

Copy `.env.example` to `.env` and add your Gemini API key:

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

If you don't have an API key:
1. Go to https://makersuite.google.com/app/apikey
2. Create a new API key
3. Paste it in `.env`

(The app will work without an API key — it will fall back to rule-based diagnostics.)

### 3. Run the App

```bash
python app.py
```

Then open your browser to:
```
http://localhost:5000
```

## 🔧 How It Works

### Metrics Collection
- **Every 5 seconds:**
  - Ping `8.8.8.8` (Google DNS) → measures latency + packet loss
  - Read `/proc/net/dev` → tracks RX/TX bytes
  - Store results in SQLite

### Anomaly Detection
- Compares current latency to 60-second baseline
- Flags issues:
  - Latency spike > 30% = congestion warning
  - Packet loss > 2% = network instability
  - Throughput drop > 20% = throttling

### AI Diagnosis
- Sends metric summary to OpenAI GPT-4o-mini
- Returns 2-3 sentence explanation of what's happening
- Falls back to rule-based response if API unavailable

### Web Interface
- Real-time metrics dashboard
- "Refresh Metrics" button
- "Get Diagnosis" button for on-demand AI analysis
- Auto-refreshes every 10 seconds

## 📊 API Endpoints

- `GET /` — Main dashboard
- `GET /api/metrics` — Current network metrics (JSON)
- `GET /api/diagnosis` — Get AI diagnosis (JSON)

## 🧪 Testing Without Hardware

This project is designed to run on real hardware with actual network connectivity. For testing/development:

- The app works on any Linux/Mac system with network connectivity
- Use the real `ping` command (not mocked)
- On Raspberry Pi: Install `iputils-ping` if needed

**For production deployment on Raspberry Pi**, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## 💰 Gemini Cost

- Gemini Pro: **Free** for up to 60 requests per minute
- Each diagnosis: ~100 tokens
- Cost per diagnosis: **$0** (within free tier)
- Essentially free for a hackathon!

## 📁 Project Structure

```
network-copilot/
├── app.py                      # Flask web server
├── metrics_collector.py        # Background metric collection
├── analyzer.py                 # Anomaly detection logic
├── llm_wrapper.py              # OpenAI integration
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── templates/
│   └── index.html              # Web UI
└── data.db                     # SQLite database (auto-created)
```

## 🚀 Deployment on Raspberry Pi

1. SSH into your Pi
2. Clone this repo
3. Follow "Quick Start" steps
4. Run `python app.py`
5. Access from any device on your network: `http://<pi-ip>:5000`

## 🎤 Demo Script for Judges

1. **Show the dashboard:** "Here's the network copilot monitoring my 5G connection in real-time."
2. **Click "Get Diagnosis":** "The AI analyzes the metrics and explains what's happening."
3. **Trigger congestion:** Run `iperf3` or a large download to artificially spike latency.
4. **Show spike detection:** "See how it detected the spike and explained the cause?"
5. **Key insight:** "This is local, privacy-preserving AI at the edge — exactly what T-Mobile wants."

## 🔐 Privacy

- All metrics collection is **local** — nothing leaves your Pi except API calls to OpenAI
- No personal data is sent to the LLM
- Metrics are stored in a local SQLite database

## 📝 Customization

### Change ping target
Edit `metrics_collector.py`, line ~25:
```python
result = subprocess.run(["ping", "-c", "4", "8.8.8.8"], ...)
# Change "8.8.8.8" to any IP
```

### Change collection interval
Edit `app.py`, line ~8:
```python
start_collection(interval=5)  # Change 5 to desired seconds
```

### Add more metrics
Edit `metrics_collector.py` to add CPU, memory, or device-specific metrics.

## 🤝 Contributing

This is a hackathon project. Feel free to fork and extend!

## 📜 License

MIT

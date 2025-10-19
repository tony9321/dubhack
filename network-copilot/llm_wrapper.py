import os
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv, find_dotenv
from analyzer import analyze_network

# Load .env from the nearest location (workspace root or current folder)
_dotenv_path = find_dotenv(usecwd=True)
load_dotenv(_dotenv_path, override=True)

# Try to import Gemini, but don't fail if not available
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# Structured logger setup (rotating file)
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

_gemini_logger = logging.getLogger('gemini')
if not _gemini_logger.handlers:
    _gemini_logger.setLevel(logging.INFO)
    _handler = RotatingFileHandler(os.path.join(LOG_DIR, 'gemini.log'), maxBytes=1_000_000, backupCount=3)
    _handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    _gemini_logger.addHandler(_handler)

def _log(msg: str, level: str = 'info'):
    line = f"[Gemini] {msg}"
    print(line)
    if level == 'error':
        _gemini_logger.error(msg)
    elif level == 'warning':
        _gemini_logger.warning(msg)
    else:
        _gemini_logger.info(msg)


def get_llm_diagnosis():
    """Get LLM-powered diagnosis of network issues using Gemini."""

    # Get current network analysis
    analysis = analyze_network()

    if not analysis:
        _log("No analysis available; returning wait message.")
        return "No network metrics available yet. Please wait for the metrics collector to gather data."

    # Prepare data for LLM
    network_data = {
        "current_latency_ms": round(analysis["current_latency"], 1),
        "baseline_latency_ms": round(analysis["baseline_latency"], 1),
        "latency_increase_percent": round(analysis["latency_spike_percent"], 1),
        "packet_loss_percent": round(analysis["packet_loss"], 1),
        "has_issues": bool(analysis.get("has_issues", False)),
        "summary": analysis.get("summary", "")
    }

    # If no API key or SDK missing, return rule-based response
    api_key = os.getenv("GEMINI_API_KEY")
    if not HAS_GEMINI:
        _log("google.generativeai not installed; using rule-based response.")
        return generate_rule_based_response(network_data, network_data["summary"])
    if not api_key:
        _log("GEMINI_API_KEY not set; using rule-based response.")
        return generate_rule_based_response(network_data, network_data["summary"])

    try:
        genai.configure(api_key=api_key)

        # Prefer widely-available models first, with fallback
        model_ids = [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro"
        ]
        model = None
        last_err = None
        chosen_model_id = None
        for mid in model_ids:
            try:
                _log(f"Attempting model '{mid}'")
                model = genai.GenerativeModel(mid)
                _log(f"Using model '{mid}'")
                chosen_model_id = mid
                break
            except Exception as me:
                last_err = me
                _log(f"Model '{mid}' unavailable: {me}")
        if model is None:
            raise RuntimeError(f"No Gemini model available: {last_err}")

        prompt = (
            "You are a network diagnostics assistant. Based on the following network metrics, "
            "provide a brief (2-3 sentence) diagnosis of what's happening with the network.\n\n"
            f"Network Data:\n- Current Latency: {network_data['current_latency_ms']}ms\n"
            f"- Baseline Latency: {network_data['baseline_latency_ms']}ms\n"
            f"- Latency Change: {network_data['latency_increase_percent']}%\n"
            f"- Packet Loss: {network_data['packet_loss_percent']}%\n\n"
            "Provide a concise, actionable explanation. If all metrics are normal, say so briefly."
        )

        # Pre-call structured log
        try:
            _log(json.dumps({
                "event": "gemini_call_start",
                "model": chosen_model_id,
                "prompt_len": len(prompt),
                "prompt_preview": prompt[:200]
            }))
        except Exception:
            pass

        start = time.time()
        response = model.generate_content(prompt)
        duration_ms = int((time.time() - start) * 1000)
        text = getattr(response, "text", None)
        if not text:
            # Some SDK versions return candidates
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = None
        # usage metadata if available
        usage = None
        try:
            usage_meta = getattr(response, 'usage_metadata', None)
            if usage_meta:
                usage = {
                    'prompt_tokens': getattr(usage_meta, 'prompt_token_count', None),
                    'candidate_tokens': getattr(usage_meta, 'candidates_token_count', None),
                    'total_tokens': getattr(usage_meta, 'total_token_count', None)
                }
        except Exception:
            usage = None
        # response id and prompt feedback (if any)
        rid = getattr(response, 'response_id', None)
        pfb = None
        try:
            fb = getattr(response, 'prompt_feedback', None)
            if fb:
                pfb = {
                    'block_reason': getattr(fb, 'block_reason', None),
                    'safety_ratings': getattr(fb, 'safety_ratings', None)
                }
        except Exception:
            pfb = None

        if text:
            try:
                _log(json.dumps({
                    "event": "gemini_call_success",
                    "model": chosen_model_id,
                    "duration_ms": duration_ms,
                    "response_len": len(text),
                    "usage": usage,
                    "response_id": rid,
                    "prompt_feedback": pfb
                }))
            except Exception:
                pass
            return text
        else:
            try:
                _log(json.dumps({
                    "event": "gemini_call_empty",
                    "model": chosen_model_id,
                    "duration_ms": duration_ms,
                    "usage": usage
                }), level='warning')
            except Exception:
                _log("Empty response from Gemini; using rule-based response.", level='warning')
            return generate_rule_based_response(network_data, network_data["summary"])

    except Exception as e:
        try:
            _log(json.dumps({
                "event": "gemini_call_error",
                "error": str(e)
            }), level='error')
        except Exception:
            _log(f"Error calling Gemini API: {e}", level='error')
        return generate_rule_based_response(network_data, network_data["summary"])

def generate_rule_based_response(network_data, summary):
    """Generate rule-based response when LLM is not available."""
    
    latency = network_data["current_latency_ms"]
    baseline = network_data["baseline_latency_ms"]
    spike = network_data["latency_increase_percent"]
    loss = network_data["packet_loss_percent"]
    
    if spike > 50 or loss > 5:
        return f"⚠️ Network degraded significantly. Latency spiked {spike:.0f}% to {latency:.1f}ms (baseline: {baseline:.1f}ms), packet loss at {loss:.1f}%. Try pausing bandwidth-heavy tasks."
    elif spike > 30 or loss > 2:
        return f"⚠️ Network showing congestion signs. Latency up {spike:.0f}% ({latency:.1f}ms), packet loss {loss:.1f}%. Monitor the situation."
    elif spike > 0 or loss > 0:
        return f"✓ Network mostly healthy with minor fluctuations. Latency {latency:.1f}ms (baseline: {baseline:.1f}ms), packet loss {loss:.1f}%."
    else:
        return f"✓ Network health is excellent. Latency stable at {latency:.1f}ms, no packet loss detected."

if __name__ == "__main__":
    diagnosis = get_llm_diagnosis()
    print(diagnosis)

def get_llm_security_analysis(snapshot: dict) -> dict:
    """Ask Gemini to analyze a compact security snapshot and return structured JSON.
    Falls back to heuristics if the model/key is unavailable or JSON parsing fails.
    """
    # Local import to avoid circulars
    try:
        from security_analysis import detect_suspects
    except Exception:
        detect_suspects = None

    # If SDK/key missing, fallback
    api_key = os.getenv("GEMINI_API_KEY")
    if not HAS_GEMINI or not api_key:
        if detect_suspects:
            return detect_suspects(snapshot)
        return {"suspected_devices": [], "global_observations": ["LLM unavailable"], "confidence": "low"}

    try:
        genai.configure(api_key=api_key)

        model_ids = [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro"
        ]
        model = None
        last_err = None
        chosen_model_id = None
        for mid in model_ids:
            try:
                _log(f"Attempting model '{mid}' for security analysis")
                model = genai.GenerativeModel(mid)
                chosen_model_id = mid
                break
            except Exception as me:
                last_err = me
                _log(f"Model '{mid}' unavailable: {me}")
        if model is None:
            raise RuntimeError(f"No Gemini model available: {last_err}")

        instruction = (
            "You are a home network security assistant. Identify devices with suspicious behavior from the provided"
            " snapshot. Consider: high outbound vs inbound ratio, sustained latency/loss threshold violations, new"
            " devices with traffic, and missing hostnames. Output STRICT JSON ONLY with this schema: "
            "{\n  \"suspected_devices\": [ { \"ip\": \"string\", \"risk_score\": 0, \"reasons\":[\"...\"], \"recommended_actions\":[\"...\"] } ],\n  \"global_observations\": [\"...\"],\n  \"confidence\": \"low|medium|high\"\n}"
        )

        content = {
            "instruction": instruction,
            "snapshot": {
                "window_seconds": snapshot.get("window_seconds"),
                "generated_at": snapshot.get("generated_at"),
                "thresholds": snapshot.get("thresholds"),
                # Truncate to top 30 devices to limit size
                "devices": snapshot.get("devices", [])[:30]
            }
        }

        prompt = (
            "Analyze the following JSON and return ONLY the required JSON schema, no extra text.\n" +
            json.dumps(content, ensure_ascii=False)
        )

        _log(json.dumps({
            "event": "security_ai_call_start",
            "model": chosen_model_id,
            "prompt_len": len(prompt)
        }))

        start = time.time()
        response = model.generate_content(prompt)
        duration_ms = int((time.time() - start) * 1000)

        text = getattr(response, "text", None)
        if not text:
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = None

        if text:
            try:
                parsed = json.loads(text)
                _log(json.dumps({
                    "event": "security_ai_call_success",
                    "model": chosen_model_id,
                    "duration_ms": duration_ms,
                    "response_len": len(text)
                }))
                return parsed
            except Exception as pe:
                _log(f"Security AI JSON parse failed: {pe}", level='warning')
        else:
            _log("Security AI empty response", level='warning')

    except Exception as e:
        _log(f"Security AI error: {e}", level='error')

    # Fallback
    if detect_suspects:
        return detect_suspects(snapshot)
    return {"suspected_devices": [], "global_observations": ["fallback used"], "confidence": "low"}

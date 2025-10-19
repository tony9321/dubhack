import os
import json
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

def _log(msg: str):
    print(f"[Gemini] {msg}")


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
            "gemini-pro",
            "gemini-1.5-flash",
            "gemini-1.5-pro"
        ]
        model = None
        last_err = None
        for mid in model_ids:
            try:
                _log(f"Attempting model '{mid}'")
                model = genai.GenerativeModel(mid)
                _log(f"Using model '{mid}'")
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

        _log("Calling Gemini generate_content()")
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)
        if not text:
            # Some SDK versions return candidates
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = None
        if text:
            _log("Received response from Gemini.")
            return text
        else:
            _log("Empty response from Gemini; using rule-based response.")
            return generate_rule_based_response(network_data, network_data["summary"])

    except Exception as e:
        _log(f"Error calling Gemini API: {e}")
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
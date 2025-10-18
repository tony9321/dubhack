import os
from dotenv import load_dotenv
from analyzer import analyze_network
import json

load_dotenv()

# Try to import Gemini, but don't fail if not available
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

def get_llm_diagnosis():
    """Get LLM-powered diagnosis of network issues using Gemini."""
    
    # Get current network analysis
    analysis = analyze_network()
    
    if not analysis:
        return "No network metrics available yet. Please wait for the metrics collector to gather data."
    
    # Prepare data for LLM
    network_data = {
        "current_latency_ms": round(analysis["current_latency"], 1),
        "baseline_latency_ms": round(analysis["baseline_latency"], 1),
        "latency_increase_percent": round(analysis["latency_spike_percent"], 1),
        "packet_loss_percent": round(analysis["packet_loss"], 1),
    }
    
    # If no API key, return rule-based response
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key or not HAS_GEMINI:
        return generate_rule_based_response(network_data, analysis["summary"])
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""You are a network diagnostics assistant. Based on the following network metrics, provide a brief (2-3 sentence) diagnosis of what's happening with the network:

Network Data:
- Current Latency: {network_data['current_latency_ms']}ms
- Baseline Latency: {network_data['baseline_latency_ms']}ms
- Latency Increase: {network_data['latency_increase_percent']}%
- Packet Loss: {network_data['packet_loss_percent']}%

Provide a natural language explanation of the network health. Keep it concise and actionable. If all metrics are normal, say so briefly."""

        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return generate_rule_based_response(network_data, analysis["summary"])

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

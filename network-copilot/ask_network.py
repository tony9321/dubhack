
#!/usr/bin/env python3
"""
CLI interface for Network Copilot
Use this for quick testing or voice integration
"""

import sys
from analyzer import analyze_network
from llm_wrapper import get_llm_diagnosis
import time

def main():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "How's my network?"
    
    print(f"\n📊 {question}\n")
    
    # Get diagnosis
    diagnosis = get_llm_diagnosis()
    print(diagnosis)
    
    # Also print raw metrics for debugging
    analysis = analyze_network()
    if analysis:
        print(f"\n[Debug] Latency: {analysis['current_latency']:.1f}ms | "
              f"Baseline: {analysis['baseline_latency']:.1f}ms | "
              f"Loss: {analysis['packet_loss']:.1f}% | "
              f"Spike: {analysis['latency_spike_percent']:.0f}%")

if __name__ == "__main__":
    main()

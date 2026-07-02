#!/usr/bin/env python3
"""
Benchmark Ollama generation speed across one or more hosts.

Usage:
    python3 ollama_benchmark.py \
        --hosts http://127.0.0.1:11434 http://192.168.1.50:11434 \
        --model llama3.1 \
        --runs 5 \
        --num-predict 200

Notes:
- Point --hosts at as many machines as you want to compare (local Debian
  server, remote Windows server, etc). Each URL should be reachable and
  running Ollama with the same model already pulled.
- The first request to each host is a warm-up (loads the model into
  RAM/VRAM) and is excluded from the timed average.
- Speed is measured via eval_count/eval_duration from Ollama's own API
  response, not wall-clock time, so remote network latency doesn't skew
  the comparison.
"""
import argparse          # Parse command-line flags (--hosts, --model, etc.)
import json              # Encode the request body and decode Ollama's JSON reply
import statistics        # mean() / stdev() for summarising the timed runs
import time              # Wall-clock timing around each request
import urllib.request    # Make HTTP POST calls without any third-party deps


def query(host, model, prompt, num_predict):
    # Build the generate endpoint URL; rstrip('/') avoids a double slash if
    # the user passes a host with a trailing '/'.
    url = f"{host.rstrip('/')}/api/generate"
    # Request body matching Ollama's /api/generate schema.
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,  # Get one complete JSON response instead of a token stream
        "options": {
            "num_predict": num_predict,  # Cap on tokens generated per run
            "temperature": 0,            # Deterministic (greedy) decoding
            "seed": 42,                  # Fixed seed so every run is reproducible
        },
    }
    # Serialise the payload to a JSON string, then to bytes (required by urllib).
    data = json.dumps(payload).encode("utf-8")
    # Passing a body makes this a POST; the header tells Ollama it's JSON.
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    start = time.time()  # Mark the start for wall-clock measurement
    # Send the request; 300s timeout covers slow model loads / long generations.
    # The 'with' block guarantees the connection is closed afterwards.
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read())  # Parse the JSON response into a dict
    wall_time = time.time() - start  # Total round-trip time including network
    # Return both the parsed response and the wall time to the caller.
    return body, wall_time


def run_benchmark(host, model, prompt, num_predict, runs):
    print(f"\n=== {host} ===")
    print("Warming up (loading model into memory)...")
    # First request loads the model into RAM/VRAM; we time it separately and
    # exclude it from the average so cold-start cost doesn't skew results.
    warmup_body, _ = query(host, model, prompt, num_predict)
    # load_duration is reported in nanoseconds; /1e9 converts to seconds.
    # .get(..., 0) defends against the field being absent in the response.
    load_s = warmup_body.get("load_duration", 0) / 1e9
    print(f"Model load time: {load_s:.2f}s")

    tok_per_sec_runs = []  # Tokens/sec for each timed run
    wall_times = []        # Wall-clock seconds for each timed run
    # Run the same prompt 'runs' times to average out per-request variation.
    for i in range(runs):
        body, wall_time = query(host, model, prompt, num_predict)
        eval_count = body.get("eval_count", 0)     # Tokens the model generated
        eval_duration = body.get("eval_duration", 1)  # Generation time in nanoseconds
        # Server-reported throughput: tokens divided by generation time (in s).
        # This ignores network latency, unlike wall_time. Guard against a zero
        # eval_duration to avoid a divide-by-zero.
        tps = eval_count / (eval_duration / 1e9) if eval_duration else 0
        tok_per_sec_runs.append(tps)
        wall_times.append(wall_time)
        # i + 1 makes the run number 1-based for human-friendly output.
        print(f"  Run {i + 1}: {tps:.2f} tok/s  ({eval_count} tokens, wall {wall_time:.2f}s)")

    # Aggregate this host's results into a dict for the final summary table.
    return {
        "host": host,
        "load_time_s": load_s,
        "avg_tokens_per_sec": statistics.mean(tok_per_sec_runs),
        # stdev needs at least two data points; fall back to 0.0 for a single run.
        "stdev_tokens_per_sec": statistics.stdev(tok_per_sec_runs) if runs > 1 else 0.0,
        "avg_wall_time_s": statistics.mean(wall_times),
    }


def main():
    # Set up the CLI parser and declare each accepted flag.
    parser = argparse.ArgumentParser(description="Benchmark Ollama generation speed across hosts")
    # nargs="+" accepts one or more space-separated URLs into a list.
    parser.add_argument("--hosts", nargs="+", required=True, help="Ollama base URLs to test")
    parser.add_argument("--model", required=True, help="Model name, e.g. llama3.1")
    parser.add_argument(
        "--prompt",
        default="Write a 300-word short story about a lighthouse keeper.",
        help="Prompt to send (kept identical across hosts)",
    )
    # type=int converts the string argument; argparse maps --num-predict to args.num_predict.
    parser.add_argument("--num-predict", type=int, default=200, help="Tokens to generate per run")
    parser.add_argument("--runs", type=int, default=5, help="Timed runs per host (after warm-up)")
    args = parser.parse_args()  # Parse sys.argv; exits with usage on bad input

    # Benchmark every host in turn, collecting one result dict per host.
    results = [
        run_benchmark(host, args.model, args.prompt, args.num_predict, args.runs)
        for host in args.hosts
    ]

    # Print a fixed-width comparison table. "=" * 64 draws a 64-char rule.
    print("\n" + "=" * 64)
    # Format spec: <32 left-aligns in 32 cols, >12/>10 right-align the numbers.
    print(f"{'Host':<32}{'Avg tok/s':>12}{'StDev':>10}{'Load(s)':>10}")
    print("=" * 64)
    for r in results:
        # Adjacent string literals are concatenated; .2f rounds to 2 decimals.
        print(
            f"{r['host']:<32}{r['avg_tokens_per_sec']:>12.2f}"
            f"{r['stdev_tokens_per_sec']:>10.2f}{r['load_time_s']:>10.2f}"
        )


# Only run main() when executed directly, not when imported as a module.
if __name__ == "__main__":
    main()

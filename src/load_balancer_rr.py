# lb_roundrobin.py → Round-Robin Load Balancer (Port 5007)
from flask import Flask, request, jsonify
import requests
import threading
import time
import itertools

app = Flask(__name__)

FOG_NODES = [
    "http://127.0.0.1:5001",
    "http://127.0.0.1:5002",
    "http://127.0.0.1:5003",
]

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB chunks
results = []
results_lock = threading.Lock()

# Global round-robin iterator (thread-safe with lock when advancing)
node_cycle = itertools.cycle(FOG_NODES)
cycle_lock = threading.Lock()

def select_node_roundrobin():
    with cycle_lock:
        return next(node_cycle)

def process_chunk(idx: int, chunk_data: bytes):
    node = select_node_roundrobin()
    start_time = time.time()

    try:
        resp = requests.post(f"{node}/task", data=chunk_data, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[RoundRobin LB] Error on node {node}: {e}")
        data = {
            "result": None,
            "key": None,
            "nonce": None,
            "processing_time": 0,
            "node_used": node.split(":")[-1],
            "error": "failed"
        }

    total_time = time.time() - start_time

    result_entry = {
        "chunk": idx,
        "node_used": int(data.get("node_used", node.split(":")[-1])),
        "result": data.get("result"),           # encrypted chunk (hex)
        "key": data.get("key"),                 # CRITICAL: forward encryption key
        "nonce": data.get("nonce"),             # CRITICAL: forward nonce
        "processing_time": data.get("processing_time", 0),
        "total_time": total_time
    }

    with results_lock:
        results.append(result_entry)


@app.route("/process_file", methods=["POST"])
def process_file():
    global results
    results = []  # Reset results for new request

    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    file = request.files["file"]
    file_content = file.read()

    # Split file into chunks in memory
    chunks = [
        file_content[i:i + CHUNK_SIZE]
        for i in range(0, len(file_content), CHUNK_SIZE)
    ]

    threads = []
    for idx, chunk in enumerate(chunks):
        t = threading.Thread(target=process_chunk, args=(idx, chunk))
        t.start()
        threads.append(t)

    # Wait for all chunks to be processed
    for t in threads:
        t.join()

    # Sort results by chunk index to preserve order
    sorted_results = sorted(results, key=lambda x: x["chunk"])

    # Optional: Print distribution summary
    node_usage = {}
    for r in sorted_results:
        node = r["node_used"]
        node_usage[node] = node_usage.get(node, 0) + 1
    print(f"[RoundRobin LB] Node distribution: {node_usage}")

    return jsonify({
        "results": sorted_results,
        "load_balancer": "round-robin",
        "node_distribution": node_usage
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "type": "roundrobin_lb",
        "port": 5007,
        "nodes": FOG_NODES
    })


if __name__ == "__main__":
    print("Round-Robin Load Balancer → http://127.0.0.1:5007")
    app.run(host="0.0.0.0", port=5007, debug=False, threaded=True)
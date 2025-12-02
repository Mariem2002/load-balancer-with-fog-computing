# lb_round_robin.py → Round Robin Load Balancer (Port 5007)
from flask import Flask, request, jsonify
import requests
import threading
import time

app = Flask(__name__)

FOG_NODES = [
    "http://127.0.0.1:5001",
    "http://127.0.0.1:5002",
    "http://127.0.0.1:5003",
]

CHUNK_SIZE = 5 * 1024 * 1024
results = []
results_lock = threading.Lock()

# --- Round Robin counter ---
rr_index = 0
rr_lock = threading.Lock()

def select_node_rr():
    global rr_index
    with rr_lock:
        node = FOG_NODES[rr_index]
        rr_index = (rr_index + 1) % len(FOG_NODES)
    return node

def process_chunk(idx: int, chunk_data: bytes):
    node = select_node_rr()
    start_time = time.time()

    try:
        resp = requests.post(f"{node}/task", data=chunk_data, timeout=60)
        resp.raise_for_status()
        data = resp.json()  
    except Exception as e:
        print(f"[RR LB] Error on node {node}: {e}")
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
        "result": data.get("result"),
        "key": data.get("key"),
        "nonce": data.get("nonce"),
        "processing_time": data.get("processing_time", 0),
        "total_time": total_time
    }

    with results_lock:
        results.append(result_entry)

@app.route("/process_file", methods=["POST"])
def process_file():
    global results
    results = []

    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    file = request.files["file"]
    file_content = file.read()

    chunks = [
        file_content[i:i + CHUNK_SIZE]
        for i in range(0, len(file_content), CHUNK_SIZE)
    ]

    threads = []
    for idx, chunk in enumerate(chunks):
        t = threading.Thread(target=process_chunk, args=(idx, chunk))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    sorted_results = sorted(results, key=lambda x: x["chunk"])
    return jsonify({"results": sorted_results})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "type": "round_robin_lb", "port": 5007})

if __name__ == "__main__":
    print("Round Robin Load Balancer → http://127.0.0.1:5007")
    app.run(host="0.0.0.0", port=5005, debug=False, threaded=True)

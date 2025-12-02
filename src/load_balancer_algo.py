# load_balancer_aes_optimized.py → Smart Load Balancer (Algo)
from flask import Flask, request, jsonify
import requests, time
from threading import Lock

app = Flask(__name__)

FOG_NODES = [
    "http://172.20.10.5:5001",
    "http://172.20.10.2:5002",
    "http://172.20.10.6:5003",
]

node_kpi = {node: None for node in FOG_NODES}
local_tasks = {node: 0 for node in FOG_NODES}
ALPHA = 0.3
LOCK = Lock()

def select_node(chunk_size):
    untested = [n for n in FOG_NODES if node_kpi[n] is None]
    if untested:
        return untested[0]

    scores = {}
    with LOCK:
        for node in FOG_NODES:
            try:
                r = requests.get(f"{node}/health", timeout=1.5)
                health = r.json()
                cpu = health.get("cpu_percent", 100)
                ram = health.get("ram_percent", 100)
                load = 1 + local_tasks[node]
            except:
                cpu = ram = 100
                load = 999

            size_factor = max(chunk_size / (50 * 1024 * 1024), 0.1)
            base_time = node_kpi[node] or 10.0
            score = base_time * load * (1 + cpu/200) * (1 + ram/200) * size_factor
            scores[node] = score

    return min(scores, key=scores.get)

@app.route("/process_file", methods=["POST"])
def process_file():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]
    content = file.read()
    chunk_size = 5 * 1024 * 1024
    num_chunks = (len(content) + chunk_size - 1) // chunk_size
    results = []

    for i in range(num_chunks):
        start = i * chunk_size
        end = start + chunk_size
        chunk = content[start:end]

        tried = set()
        while len(tried) < len(FOG_NODES):
            node = select_node(len(chunk))
            if node in tried:
                node = [n for n in FOG_NODES if n not in tried][0]
            tried.add(node)

            total_start = time.time()
            with LOCK:
                local_tasks[node] += 1

            try:
                resp = requests.post(f"{node}/task", data=chunk, timeout=60)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                with LOCK:
                    local_tasks[node] -= 1
                continue  # retry next node

            elapsed = time.time() - total_start

            with LOCK:
                old = node_kpi[node]
                new_time = data.get("processing_time", elapsed)
                node_kpi[node] = new_time if old is None else ALPHA * new_time + (1 - ALPHA) * old
                local_tasks[node] -= 1

            port = node.split(":")[-1]
            results.append({
                "chunk": i,
                "node_used": int(port),
                "result": data["result"],
                "key": data["key"],           # CRITICAL
                "nonce": data["nonce"],       # CRITICAL
                "processing_time": data.get("processing_time", 0),
                "total_time": elapsed
            })
            break  # success

        else:
            # All nodes failed
            results.append({"chunk": i, "error": "all nodes failed"})

    return jsonify({"results": results})

@app.route("/nodes_status")
def nodes_status():
    status = {}
    for node in FOG_NODES:
        try:
            r = requests.get(f"{node}/health", timeout=2)
            h = r.json()
            status[node] = {k: h.get(k) for k in ["cpu_percent", "ram_percent", "tasks_running"]}
            status[node]["kpi"] = round(node_kpi[node], 3) if node_kpi[node] else None
        except:
            status[node] = {"error": "offline"}
    return jsonify(status)

if __name__ == "__main__":
    print("Smart Load Balancer (Algo) → http://127.0.0.1:5006")
    app.run(host="0.0.0.0", port=5006, debug=False)
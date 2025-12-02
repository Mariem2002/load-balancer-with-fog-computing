# fog_node.py

from flask import Flask, request, jsonify, Response
from prometheus_client import start_http_server, Gauge
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, threading, time, psutil
from prometheus_client import Counter

app = Flask(__name__)

cpu_gauge = Gauge('fog_cpu_percent', 'CPU usage percent')
tasks_gauge = Gauge('fog_tasks_running', 'Number of tasks running')
ram_gauge = Gauge('fog_ram_percent', 'RAM usage percent')
chunks_counter = Counter('chunks_processed_total', 'Total chunks processed', ['node', 'file'])

tasks_running = 0
lock = threading.Lock()

PORT = int(os.environ.get("PORT", "5002"))
METRICS_PORT = 8000 + (PORT % 1000)

def update_metrics():
    global tasks_running
    while True:
        cpu_gauge.set(psutil.cpu_percent(interval=0.1))
        ram_gauge.set(psutil.virtual_memory().percent)
        tasks_gauge.set(tasks_running)
        time.sleep(1)

threading.Thread(target=update_metrics, daemon=True).start()
start_http_server(METRICS_PORT)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "port": PORT,
        "cpu_percent": psutil.cpu_percent(interval=0.05),
        "ram_percent": psutil.virtual_memory().percent,
        "tasks_running": tasks_running
    })
@app.route('/metrics')
def metrics():
    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory().used / (1024 * 1024)

    data = f"""
# HELP cpu_usage CPU usage percentage
# TYPE cpu_usage gauge
cpu_usage {cpu}

# HELP memory_usage Memory usage in MB
# TYPE memory_usage gauge
memory_usage {memory}
"""

    return Response(data, mimetype="text/plain")

@app.route("/task", methods=["POST"])
def task():
    global tasks_running
    chunk = request.data

    with lock:
        tasks_running += 1

    start_time = time.time()

    try:
        key = AESGCM.generate_key(bit_length=128)
        aes = AESGCM(key)

        nonce = os.urandom(12)
        ciphertext = aes.encrypt(nonce, chunk, None)

        processing_time = time.time() - start_time
        file_name = request.headers.get('X-File-Name', 'unknown')
        chunks_counter.labels(node=str(PORT), file=file_name).inc()


        return jsonify({
            "result": ciphertext.hex(),
            "nonce": nonce.hex(),
            "key": key.hex(),
            "processing_time": processing_time,
            "node_used": PORT
        })

    finally:
        with lock:
            tasks_running -= 1


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
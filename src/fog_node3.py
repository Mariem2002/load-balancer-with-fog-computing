# fog_node.py
from flask import Flask, request, jsonify
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import psutil, os, threading, time

app = Flask(__name__)
PORT = int(os.environ.get("PORT", "5003"))
tasks_running = 0
lock = threading.Lock()

def update_metrics():
    while True:
        time.sleep(1)

threading.Thread(target=update_metrics, daemon=True).start()

@app.route("/health")
def health():
    global tasks_running
    return jsonify({
        "port": PORT,
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "tasks_running": tasks_running
    })

@app.route("/task", methods=["POST"])
def encrypt_chunk():
    global tasks_running
    with lock:
        tasks_running += 1

    start = time.time()
    data = request.data

    key = AESGCM.generate_key(bit_length=256)
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, data, None)

    processing_time = time.time() - start

    with lock:
        tasks_running -= 1

    return jsonify({
        "result": ciphertext.hex(),
        "key": key.hex(),
        "nonce": nonce.hex(),
        "processing_time": processing_time,
        "node_used": PORT
    })

if __name__ == "__main__":
    print(f"Fog Node démarré sur le port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
# frontend_lb.py
from flask import Flask, request, jsonify, render_template_string, send_from_directory
import requests, os, json

app = Flask(__name__)

UPLOAD_FOLDER = "uploads_client"
ENCRYPTED_FOLDER = "encrypted"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ENCRYPTED_FOLDER, exist_ok=True)

LB_URLS = {
    "random": "http://127.0.0.1:5005",
    "algo": "http://127.0.0.1:5006",
    "round_robin": "http://127.0.0.1:5007"
}

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB

HTML_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Fog Encryption Load Balancer</title>
    <style>
        body {font-family: 'Segoe UI', sans-serif; background: #f4f6f9; margin:0; padding:20px; color:#333;}
        h2 {text-align:center; color:#4e4376; margin-bottom:30px;}
        .container {max-width: 1000px; margin: auto; background:white; padding:30px; border-radius:15px; box-shadow:0 10px 30px rgba(0,0,0,0.1);}
        .upload-section {display:flex; justify-content:center; gap:15px; flex-wrap:wrap; margin-bottom:25px;}
        input[type=file], select, button {padding:12px; border-radius:10px; font-size:16px;}
        input[type=file], select {border:2px solid #ddd;}
        button {background: linear-gradient(135deg,#667eea,#764ba2); color:white; border:none; cursor:pointer; font-weight:bold; box-shadow:0 5px 15px rgba(0,0,0,0.2); transition:0.3s;}
        button:hover {transform:translateY(-3px); box-shadow:0 8px 20px rgba(0,0,0,0.3);}
        table {width:100%; margin-top:20px; border-collapse:collapse; background:white; box-shadow:0 5px 15px rgba(0,0,0,0.1); border-radius:10px; overflow:hidden;}
        th {background: linear-gradient(135deg,#667eea,#764ba2); color:white; padding:15px;}
        td, th {padding:12px; text-align:center; border-bottom:1px solid #eee;}
        tr:hover {background:#f8f9ff;}
        .bar {height:24px; border-radius:12px; background:linear-gradient(90deg,#667eea,#764ba2); color:white; line-height:24px; font-weight:bold;}
        #downloadBtn {display:none; background:linear-gradient(135deg,#11998e,#38ef7d); margin-top:20px;}
    </style>
</head>
<body>
<div class="container">
    <h2>Chiffrement Distribué via Fog Nodes</h2>
    <div class="upload-section">
        <input type="file" id="fileInput" required>
        <select id="lbType">
            <option value="random">Random</option>
            <option value="round_robin">Round Robin</option>
            <option value="algo">Algo (Smart)</option>
        </select>
        <button onclick="uploadFile()">Chiffrer</button>
        <button onclick="getMetrics()">Actualiser Metrics</button>
    </div>

    <div id="status" style="text-align:center; font-weight:bold; margin:15px 0;"></div>

    <h3>Résultats des Chunks</h3>
    <table><thead><tr><th>Chunk</th><th>Nœud</th><th>Traitement (s)</th><th>Total (s)</th></tr></thead><tbody id="results"></tbody></table>

    <h3 style="margin-top:30px;">Métriques des Nœuds Fog</h3>
    <table><thead><tr><th>Port</th><th>CPU %</th><th>RAM %</th><th>Tâches</th></tr></thead><tbody id="metrics"></tbody></table>

    <div style="text-align:center; margin-top:30px;">
        <button id="downloadBtn" onclick="window.location.href=document.getElementById('encLink').href">
            Télécharger le fichier chiffré (.enc)
        </button>
        <a id="encLink" style="display:none;"></a>
    </div>
</div>

<script>
async function uploadFile() {
    const file = document.getElementById("fileInput").files[0];
    if (!file) return alert("Sélectionnez un fichier !");
    const lbType = document.getElementById("lbType").value;
    const form = new FormData();
    form.append("file", file);
    form.append("lb_type", lbType);

    document.getElementById("status").innerText = "Envoi et chiffrement en cours...";

    try {
        const res = await fetch("/send_file", {method: "POST", body: form});
        const data = await res.json();
        if (data.error) throw data.error;

        document.getElementById("status").innerText = `Chiffrement terminé ! ${data.results.length} chunks traités.`;
        displayResults(data.results);
        document.getElementById("encLink").href = data.encrypted_file_url;
        document.getElementById("encLink").download = file.name + ".enc";
        document.getElementById("downloadBtn").style.display = "inline-block";
    } catch (e) {
        document.getElementById("status").innerText = "Erreur : " + e;
    }
}

function displayResults(results) {
    const tbody = document.getElementById("results");
    tbody.innerHTML = "";
    results.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${r.chunk}</td><td>${r.node_used}</td><td>${r.processing_time.toFixed(3)}</td><td>${r.total_time.toFixed(3)}</td>`;
        tbody.appendChild(tr);
    });
}

async function getMetrics() {
    try {
        const res = await fetch("/metrics");
        const nodes = await res.json();
        const tbody = document.getElementById("metrics");
        tbody.innerHTML = "";
        nodes.forEach(n => {
            const tr = document.createElement("tr");
            if (n.error) {
                tr.innerHTML = `<td>${n.port || n.node}</td><td colspan="3">Hors ligne</td>`;
            } else {
                const cpuBar = `<div class="bar" style="width:${n.cpu_percent}%">${n.cpu_percent}%</div>`;
                const ramBar = `<div class="bar" style="width:${n.ram_percent}%">${n.ram_percent}%</div>`;
                tr.innerHTML = `<td>${n.port}</td><td>${cpuBar}</td><td>${ramBar}</td><td>${n.tasks_running}</td>`;
            }
            tbody.appendChild(tr);
        });
    } catch(e) { console.error(e); }
}
setInterval(getMetrics, 2000);
getMetrics();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/send_file", methods=["POST"])
def send_file():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier"}), 400

    file = request.files["file"]
    filename = file.filename
    temp_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(temp_path)

    lb_type = request.form.get("lb_type", "random")
    lb_url = LB_URLS.get(lb_type, LB_URLS["random"])

    try:
        with open(temp_path, "rb") as f:
            files = {"file": (filename, f)}
            data = {"lb_type": lb_type}
            resp = requests.post(f"{lb_url}/process_file", files=files, data=data, timeout=300)
            resp.raise_for_status()
            result = resp.json()
    except Exception as e:
        return jsonify({"error": f"Load balancer error: {str(e)}"}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # Reconstruct REAL encrypted file
    encrypted_path = os.path.join(ENCRYPTED_FOLDER, filename + ".enc")
    with open(encrypted_path, "wb") as out:
        for chunk in sorted(result["results"], key=lambda x: x["chunk"]):
            out.write(bytes.fromhex(chunk["result"]))

    # Save metadata (keys + nonces)
    meta_path = os.path.join(ENCRYPTED_FOLDER, filename + ".meta.json")
    with open(meta_path, "w") as mf:
        json.dump({"chunks": [
            {"chunk": r["chunk"], "key": r["key"], "nonce": r["nonce"]}
            for r in result["results"]
        ]}, mf, indent=2)

    return jsonify({
        "results": result["results"],
        "encrypted_file_url": f"/download/{filename}.enc"
    })

@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(ENCRYPTED_FOLDER, filename, as_attachment=True)

@app.route("/metrics")
def metrics():
    nodes = ["http://127.0.0.1:5001", "http://127.0.0.1:5002", "http://127.0.0.1:5003"]
    data = []
    for url in nodes:
        try:
            r = requests.get(f"{url}/health", timeout=2)
            r.raise_for_status()
            info = r.json()
            info["port"] = info.get("port", url.split(":")[-1])
            data.append(info)
        except:
            data.append({"port": url.split(":")[-1], "error": True})
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, debug=False)
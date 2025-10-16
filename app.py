from flask import Flask, request, jsonify
import os, requests, json, base64, time, re

app = Flask(__name__)

MY_SECRET = os.getenv("MY_SECRET")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USER = os.getenv("GITHUB_USER")
GITHUB_API = "https://api.github.com"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def safe_repo_name(email, task):
    base = f"{email.split('@')[0]}-{task}"
    base = re.sub(r'[^a-zA-Z0-9-_]', '-', base)
    return base[:70]

def get_file_sha(owner, repo, path):
    r = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}", headers=headers)
    if r.status_code == 200:
        return r.json()["sha"]
    return None

def put_file(owner, repo, path, content, message):
    content_b64 = base64.b64encode(content.encode()).decode()
    sha = get_file_sha(owner, repo, path)
    data = {"message": message, "content": content_b64}
    if sha:
        data["sha"] = sha
    r = requests.put(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}", headers=headers, json=data)
    r.raise_for_status()

def create_repo(repo_name, description):
    r = requests.post(f"{GITHUB_API}/user/repos", headers=headers, json={
        "name": repo_name,
        "description": description,
        "private": False
    })
    if r.status_code not in (201, 422):  # 422 means already exists
        r.raise_for_status()

def enable_pages(owner, repo):
    r = requests.post(f"{GITHUB_API}/repos/{owner}/{repo}/pages", headers=headers, json={
        "source": {"branch": "main", "path": "/"}
    })
    return r.status_code in (201, 204, 422)

def notify_evaluation(url, payload):
    delay = 1
    for _ in range(6):
        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay)
        delay *= 2
    return False

@app.route("/")
def home():
    return "Auto-builder API running"

@app.route("/api-endpoint", methods=["POST"])
def api():
    data = request.get_json(force=True)
    required = ["email", "secret", "task", "round", "nonce", "brief", "evaluation_url"]
    for k in required:
        if k not in data:
            return jsonify({"error": f"missing {k}"}), 400
    if data["secret"] != MY_SECRET:
        return jsonify({"error": "invalid secret"}), 403

    email = data["email"]
    task = data["task"]
    brief = data["brief"]
    evaluation_url = data["evaluation_url"]
    round_ = int(data["round"])
    repo_name = safe_repo_name(email, task)
    owner = GITHUB_USER

    # Create repo if needed
    create_repo(repo_name, f"Auto-generated for {task}")

    # Create simple index.html
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{task}</title></head>
<body>
<h1>{task}</h1>
<p>{brief}</p>
</body></html>"""

    put_file(owner, repo_name, "index.html", html, "update index.html")

    enable_pages(owner, repo_name)
    pages_url = f"https://{owner}.github.io/{repo_name}/"

    notify_evaluation(evaluation_url, {"url": pages_url, "nonce": data["nonce"]})

    return jsonify({"status": "accepted", "repo_name": repo_name, "url": pages_url})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

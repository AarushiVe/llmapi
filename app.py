from flask import Flask, request, jsonify
import os
import base64
import requests
import json
from datetime import datetime

app = Flask(__name__)
GITHUB_USER = os.environ.get("GITHUB_USER")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
SECRET = os.environ.get("SECRET")

def github_put_file(repo, path, content, commit_message):
    api = f"https://api.github.com/repos/{GITHUB_USER}/{repo}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    # check if file exists
    existing = requests.get(api, headers=headers)
    sha = existing.json().get("sha") if existing.status_code == 200 else None

    data = {
        "message": commit_message,
        "content": base64.b64encode(content.encode("utf-8")).decode(),
    }
    if sha:
        data["sha"] = sha

    r = requests.put(api, headers=headers, json=data)
    r.raise_for_status()

    return r.json()["commit"]["sha"]


# -----------------------------------------------------------
# Enable GitHub Pages
# -----------------------------------------------------------
def enable_pages(repo):
    api = f"https://api.github.com/repos/{GITHUB_USER}/{repo}/pages"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    data = {
        "source": {
            "branch": "main",
            "path": "/"
        }
    }
    r = requests.post(api, headers=headers, json=data)
    if r.status_code not in (201, 204):
        print("Pages enable error:", r.text)
@app.route("/api-endpoint", methods=["POST"])
def api_endpoint():
    req = request.get_json(force=True)

    # 1. Secret check
    if req.get("secret") != SECRET:
        return jsonify({"error": "Invalid secret"}), 401

    email = req["email"]
    task = req["task"]
    round_num = req.get("round", 1)
    nonce = req["nonce"]
    brief = req["brief"]
    evaluation_url = req["evaluation_url"]
    repo = task.replace(" ", "-").lower()
    repo_url = f"https://github.com/{GITHUB_USER}/{repo}"
    pages_url = f"https://{GITHUB_USER}.github.io/{repo}/"

    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    if round_num == 1:
        create = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json={"name": repo, "private": False}
        )
        if create.status_code >= 300 and create.status_code != 422:
            return jsonify({"error": "Repo creation failed"}), 500
    html = f"""
    <html>
      <body>
        <h1>{brief}</h1>
      </body>
    </html>
    """

    commit_sha1 = github_put_file(repo, "index.html", html, f"Round {round_num} update")
    readme = f"# {repo}\n\n{brief}\n\nMIT License"
    commit_sha2 = github_put_file(repo, "README.md", readme, "Update README")
    license_txt = f"""MIT License

Copyright (c) 2025 {GITHUB_USER}

Permission is hereby granted, free of charge, to any person obtaining a copy...
"""
    commit_sha3 = github_put_file(repo, "LICENSE", license_txt, "Add MIT License")
    if round_num == 1:
        enable_pages(repo)
    commit_sha = commit_sha3
    notify = {
        "email": email,
        "task": task,
        "round": round_num,
        "nonce": nonce,
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url
    }

    try:
        requests.post(evaluation_url, json=notify, timeout=5)
    except:
        pass

    return jsonify({
        "repo_name": repo,
        "round": round_num,
        "status": "ok",
        "repo_url": repo_url,
        "pages_url": pages_url,
        "commit_sha": commit_sha
    }), 200


if __name__ == "__main__":
    app.run()

from flask import Flask, request, jsonify
import os
import json
import requests
import base64
from datetime import datetime

app = Flask(__name__)

# --- Config ---
GITHUB_USER = os.environ.get("GITHUB_USER")  # e.g., AarushiVe
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # Personal Access Token
SECRET = os.environ.get("SECRET")  # Secret for verification

# --- Helper functions ---
def save_tasks_log(log_entry):
    """Append a task log to tasks.json"""
    try:
        if os.path.exists("tasks.json"):
            with open("tasks.json", "r") as f:
                data_log = json.load(f)
        else:
            data_log = []
        data_log.append(log_entry)
        with open("tasks.json", "w") as f:
            json.dump(data_log, f, indent=2)
    except Exception as e:
        print("Log write error:", e)

def decode_attachments(attachments, repo_dir):
    """Decode base64 attachments into repo folder"""
    for attachment in attachments:
        name = attachment.get("name")
        data_url = attachment.get("url")
        if not name or not data_url:
            continue
        try:
            data = data_url.split(",")[1]
            content = base64.b64decode(data)
            path = os.path.join(repo_dir, name)
            with open(path, "wb") as f:
                f.write(content)
        except Exception as e:
            print(f"Attachment decode error ({name}):", e)

# --- Main API endpoint ---
@app.route("/api-endpoint", methods=["POST"])
def api_endpoint():
    try:
        req = request.get_json(force=True)
        email = req.get("email")
        secret = req.get("secret")
        task = req.get("task")
        round_num = req.get("round", 1)
        nonce = req.get("nonce")
        brief = req.get("brief", "")
        checks = req.get("checks", [])
        evaluation_url = req.get("evaluation_url")
        attachments = req.get("attachments", [])

        # --- 1️⃣ Verify secret ---
        if secret != SECRET:
            return jsonify({"error": "Invalid secret"}), 401

        # --- 2️⃣ Generate repo name ---
        repo_name = task.replace(" ", "-").lower()
        pages_url = f"https://{GITHUB_USER}.github.io/{repo_name}/"
        repo_dir = f"./{repo_name}"

        # --- 3️⃣ Create or update repo locally ---
        if not os.path.exists(repo_dir):
            os.makedirs(repo_dir)
        # Save a minimal HTML page based on brief (placeholder)
        with open(os.path.join(repo_dir, "index.html"), "w") as f:
            f.write(f"<html><body><h1>{brief}</h1></body></html>")

        # --- 4️⃣ Handle attachments ---
        decode_attachments(attachments, repo_dir)

        # --- 5️⃣ Write README.md ---
        readme_text = f"# {repo_name}\n\n{brief}\n\nMIT License"
        with open(os.path.join(repo_dir, "README.md"), "w") as f:
            f.write(readme_text)

        # --- 6️⃣ Add MIT LICENSE ---
        mit_text = """MIT License

Copyright (c) 2025 {user}

Permission is hereby granted, free of charge, to any person...
"""
        with open(os.path.join(repo_dir, "LICENSE"), "w") as f:
            f.write(mit_text.replace("{user}", GITHUB_USER))

        # --- 7️⃣ Push to GitHub ---
        # Using GitHub API to create/update repo
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        repo_api = f"https://api.github.com/repos/{GITHUB_USER}/{repo_name}"
        res = requests.get(repo_api, headers=headers)
        if res.status_code == 404:
            # Create repo
            data = {"name": repo_name, "private": False, "auto_init": True}
            r = requests.post("https://api.github.com/user/repos", headers=headers, json=data)
            if r.status_code >= 300:
                return jsonify({"error": f"GitHub repo creation failed: {r.text}"}), 500
        # Commit files using PyGithub or direct API (simplified here as note)
        # In practice, you may use git CLI or PyGithub to push all files

        # --- 8️⃣ Notify evaluation URL ---
        if evaluation_url:
            payload = {
                "email": email,
                "task": task,
                "round": round_num,
                "nonce": nonce,
                "repo_url": f"https://github.com/{GITHUB_USER}/{repo_name}",
                "commit_sha": "latest",
                "pages_url": pages_url
            }
            try:
                r = requests.post(evaluation_url, json=payload, headers={"Content-Type": "application/json"})
                r.raise_for_status()
            except Exception as e:
                print("Evaluation notify failed:", e)

        # --- 9️⃣ Log the task ---
        log_entry = {
            "email": email,
            "task": task,
            "round": round_num,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "repo_url": f"https://github.com/{GITHUB_USER}/{repo_name}",
            "pages_url": pages_url
        }
        save_tasks_log(log_entry)

        return jsonify({
            "repo_name": repo_name,
            "round": round_num,
            "status": "updated" if round_num == 2 else "accepted",
            "url": pages_url
        }), 200

    except Exception as e:
        print("Internal error:", e)
        return jsonify({"error": str(e)}), 500


# --- Optional logs endpoint ---
@app.route("/logs", methods=["GET"])
def logs():
    if os.path.exists("tasks.json"):
        with open("tasks.json") as f:
            return f.read(), 200, {"Content-Type": "application/json"}
    return jsonify({"message": "No logs yet"}), 200


# --- Run ---
if __name__ == "__main__":
    app.run(debug=True)

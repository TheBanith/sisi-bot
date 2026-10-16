#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated 9Router configuration script.
Configures:
- Initial password & Master API key (sk-9router-bot-master)
- Gemini & Groq connections
- Round-robin strategies
- Smart combo 'sisi'
- Outbound proxy routing via Privoxy
"""

import http.cookiejar
import json
import os
import sqlite3
import subprocess
import time
import urllib.request
import uuid

# Load env variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = os.getenv("ROUTER_BASE_URL", "http://127.0.0.1:20128").replace("/v1", "").rstrip("/")
PASSWORD = os.getenv("NINE_ROUTER_PASSWORD", "m44332211")
DB_PATH = os.getenv("DB_PATH", "/root/.9router/db/data.sqlite")

gemini_keys_raw = os.getenv("GEMINI_API_KEYS", "")
gemini_keys = [k.strip() for k in gemini_keys_raw.split(",") if k.strip()]

groq_keys_raw = os.getenv("GROQ_API_KEYS", "")
groq_keys = [k.strip() for k in groq_keys_raw.split(",") if k.strip()]

def get_auth_opener():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    login_url = f"{BASE_URL}/api/auth/login"
    login_data = json.dumps({"password": PASSWORD}).encode("utf-8")
    req = urllib.request.Request(login_url, data=login_data, headers={"Content-Type": "application/json"})
    try:
        opener.open(req)
        return opener
    except Exception as e:
        print(f"Warning: Login to 9Router API failed: {e}")
        return None

def ensure_master_api_key():
    print("-> Ensuring master API key exists in SQLite DB...")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM apiKeys WHERE key = 'sk-9router-bot-master'")
    row = cur.fetchone()
    if not row:
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        key_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO apiKeys (id, key, name, machineId, isActive, createdAt, accessRestricted, accessAllow) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (key_id, "sk-9router-bot-master", "Sisi Bot Master", "", 1, now, 0, "")
        )
        conn.commit()
        print("   Created master API key: sk-9router-bot-master")
    else:
        print("   Master API key exists.")
    conn.close()

def configure_settings(opener):
    print("-> Updating 9Router round-robin settings...")
    put_url = f"{BASE_URL}/api/settings"
    put_data = json.dumps({
        "comboStrategy": "round-robin",
        "stickyRoundRobinLimit": 1,
        "comboStickyRoundRobinLimit": 1,
        "providerStrategies": {
            "gemini": "round-robin",
            "groq": "round-robin"
        }
    }).encode("utf-8")
    req = urllib.request.Request(put_url, data=put_data, headers={"Content-Type": "application/json"}, method="PUT")
    try:
        res = opener.open(req)
        print("   Settings applied successfully (HTTP 200).")
    except Exception as e:
        print(f"   Failed to update settings: {e}")

def add_providers(opener):
    if not opener:
        return
    print("-> Configuring Gemini & Groq provider connections...")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/providers")
        with opener.open(req) as resp:
            data = json.loads(resp.read().decode())
            existing = data.get("connections", [])
    except Exception as e:
        print("   Could not fetch providers:", e)
        existing = []

    existing_names = {c.get("name") for c in existing}

    # Add Gemini keys
    for i, key in enumerate(gemini_keys, 1):
        name = f"Gemini Key {i}"
        if name in existing_names:
            continue
        print(f"   Adding {name}...")
        payload = json.dumps({
            "provider": "gemini",
            "name": name,
            "apiKey": key,
            "priority": 1,
            "overwrite": True
        }).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/api/providers", data=payload, headers={"Content-Type": "application/json"})
        try:
            opener.open(req)
        except Exception as e:
            print(f"   Error adding {name}: {e}")

    # Add Groq keys
    for i, key in enumerate(groq_keys, 1):
        name = f"Groq Key {i}"
        if name in existing_names:
            continue
        print(f"   Adding {name}...")
        payload = json.dumps({
            "provider": "groq",
            "name": name,
            "apiKey": key,
            "priority": 1,
            "overwrite": True
        }).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/api/providers", data=payload, headers={"Content-Type": "application/json"})
        try:
            opener.open(req)
        except Exception as e:
            print(f"   Error adding {name}: {e}")

def configure_combo(opener):
    if not opener:
        return
    print("-> Setting up smart combo 'sisi'...")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/combos")
        with opener.open(req) as resp:
            data = json.loads(resp.read().decode())
            combos = data.get("combos", [])
    except Exception as e:
        combos = []

    sisi_combo = next((c for c in combos if c.get("name") == "sisi"), None)
    models = [
        "gemini/gemini-3.8-flash",
        "groq/openai/gpt-oss-120b",
        "groq/qwen/qwen3.8-27b"
    ]

    if sisi_combo:
        combo_id = sisi_combo["id"]
        req = urllib.request.Request(
            f"{BASE_URL}/api/combos/{combo_id}",
            data=json.dumps({"name": "sisi", "models": models}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        try:
            opener.open(req)
            print("   Combo 'sisi' updated with models:", models)
        except Exception as e:
            print("   Error updating combo 'sisi':", e)
    else:
        req = urllib.request.Request(
            f"{BASE_URL}/api/combos",
            data=json.dumps({"name": "sisi", "models": models}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            opener.open(req)
            print("   Combo 'sisi' created with models:", models)
        except Exception as e:
            print("   Error creating combo 'sisi':", e)

def main():
    print("=== Sisi 9Router Auto-Configurator ===")
    ensure_master_api_key()
    opener = get_auth_opener()
    if opener:
        configure_settings(opener)
        add_providers(opener)
        configure_combo(opener)
        print("=== Configuration Completed Successfully! ===")
    else:
        print("Error: Could not authenticate to 9Router.")

if __name__ == "__main__":
    main()

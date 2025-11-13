#!/usr/bin/env python3
import os
import sys
import json
import requests
import re

DEBUG = os.environ.get("NETALERTX_DEBUG") == "1"

def debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr)

# --- API Request ---
def get_devices(api_url, api_key):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("devices", [])
    except requests.exceptions.RequestException as e:
        sys.stderr.write(f"API request failed: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Invalid JSON from API: {e}\n")
        sys.exit(1)

# --- Kommentare parsen ---
def parse_devcomments(comments):
    tags = []
    vars_dict = {}
    if comments:
        for part in comments.split(";"):
            part = part.strip()
            if part.startswith("TAGS="):
                tags = [t.strip() for t in part[5:].split(",") if t.strip()]
            elif part.startswith("VARS_"):
                key, _, value = part.partition("=")
                key = re.sub(r"[^a-zA-Z0-9_]", "_", key[5:])
                vars_dict[key] = value.strip()
    return tags, vars_dict

# --- Inventory aufbauen ---
def build_inventory(hosts):
    inventory = {"_meta": {"hostvars": {}}, "all": {"children": []}}

    for host in hosts:
        fqdn = host.get("devFQDN") or host.get("devName")
        if not fqdn:
            continue

        fqdn = fqdn.rstrip(".")
        ansible_host = host.get("devLastIP")
        comments = host.get("devComments", "")
        tags, vars_dict = parse_devcomments(comments)

        if not tags:
            continue  # nur Hosts mit Tags übernehmen

        # Hostvars setzen
        inventory["_meta"]["hostvars"][fqdn] = {"ansible_host": ansible_host, **vars_dict}
        debug(f"Host {fqdn} -> tags: {tags}, vars: {vars_dict}")

        # Tags als Gruppen anlegen
        for tag in tags:
            if tag in ["_meta", "all"]:
                continue
            if tag not in inventory:
                inventory[tag] = {"hosts": []}
            if "hosts" not in inventory[tag]:
                inventory[tag]["hosts"] = []
            inventory[tag]["hosts"].append(fqdn)

    # Kinderliste setzen
    inventory["all"]["children"] = [tag for tag in inventory.keys() if tag not in ["_meta", "all"]]

    return inventory

# --- Main ---
def main():
    api_host = os.environ.get("NETALERTX_HOST") or "localhost"
    api_port = os.environ.get("NETALERTX_PORT") or "20212"
    api_key = os.environ.get("NETALERTX_TOKEN")

    if not api_key:
        sys.stderr.write("Error: NETALERTX_TOKEN ist nicht gesetzt\n")
        sys.exit(1)

    api_url = f"http://{api_host}:{api_port}/devices"
    debug(f"API URL: {api_url}")

    devices = get_devices(api_url, api_key)
    inventory = build_inventory(devices)

    print(json.dumps(inventory, indent=2))

if __name__ == "__main__":
    main()


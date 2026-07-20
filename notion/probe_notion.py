#!/usr/bin/env python3
"""
Probe Notion v3 search endpoint with different body formats.
Run: TOKEN_V2=xxx SPACE_ID=321f1b322cf980379ef4db13337b14c1 python3 probe_notion.py
"""
import os, sys, re, requests, json

TOKEN_V2 = os.environ.get("TOKEN_V2", "")
SPACE_ID = os.environ.get("SPACE_ID", "")
if not TOKEN_V2 or not SPACE_ID:
    print("Need TOKEN_V2 and SPACE_ID"); sys.exit(1)

m = re.search(r"([0-9a-f]{32})", SPACE_ID.replace("-",""))
h = m.group(1)
UUID = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

HDR = {"cookie": f"token_v2={TOKEN_V2}", "content-type": "application/json"}
BASE = "https://www.notion.so/api/v3"

attempts = [
    # 1: no filters at all
    ("no filters", {
        "query": "", "spaceId": UUID, "limit": 5
    }),
    # 2: flat isDeletedOnly
    ("flat isDeletedOnly", {
        "query": "", "spaceId": UUID, "limit": 5,
        "isDeletedOnly": True
    }),
    # 3: filters object minimal
    ("filters.isDeletedOnly only", {
        "query": "", "spaceId": UUID, "limit": 5,
        "filters": {"isDeletedOnly": True}
    }),
    # 4: full old-style filters
    ("full old filters", {
        "query": "", "spaceId": UUID, "limit": 5,
        "filters": {
            "isDeletedOnly": True, "excludeTemplates": False,
            "isNavigableOnly": False, "requireEditPermissions": False,
            "ancestors": [], "createdBy": [], "editedBy": [],
            "lastEditedTime": {}, "createdTime": {}
        }
    }),
    # 5: no spaceId
    ("no spaceId", {
        "query": "", "limit": 5,
        "filters": {"isDeletedOnly": True}
    }),
    # 6: source field
    ("source:workspace", {
        "query": "", "spaceId": UUID, "limit": 5,
        "source": "workspace",
        "filters": {"isDeletedOnly": True}
    }),
    # 7: type field
    ("type:BlocksInSpace", {
        "query": "", "spaceId": UUID, "limit": 5,
        "type": "BlocksInSpace",
        "filters": {"isDeletedOnly": True}
    }),
]

for name, body in attempts:
    r = requests.post(f"{BASE}/search", headers=HDR, json=body)
    status = r.status_code
    snippet = r.text[:120].replace("\n","")
    marker = "OK" if status == 200 else "FAIL"
    print(f"[{marker}] {name:35s} {status}  {snippet}")

print("\nDone.")
import json
import os
import time
import requests

API_URL = os.environ["API_URL"]
API_TOKEN = os.environ["API_TOKEN"]

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
})

def send_event(event):
    for attempt in range(5):
        response = session.post(
            API_URL,
            json=event,
            timeout=(5, 20),
        )

        if response.status_code == 201:
            return True

        if response.status_code == 429:
            continue

        if response.status_code >= 500:
            time.sleep(2 ** attempt)
            continue

        response.raise_for_status()

    return False

with open("events.jsonl", "r", encoding="utf-8") as handle:
    for line in handle:
        event = json.loads(line)
        send_event(event)

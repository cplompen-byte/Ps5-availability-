#!/usr/bin/env python3
"""Bewaakt PlayStation-productpagina's en stuurt een ntfy-pushmelding bij wijzigingen."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import requests

PRODUCTS = {
    "PS5 Slim (refurbished)": "https://www.playstation.com/nl-nl/ps5/certified-refurbished-ps5-slim/product/PSD001-PSDE00233_59-PS5GRADEDCLIZSLE/",
    "PS5 console (refurbished)": "https://www.playstation.com/nl-nl/ps5/certified-refurbished/product/PSD001-PSDE01840_63-PS5GRADEDCEC7XZE/",
    "PS5 Slim Digital Edition (refurbished)": "https://www.playstation.com/nl-nl/ps5/certified-refurbished-ps5-slim-digital-edition/product/PSD001-PSDE00234_23-PS5GRADEDDMBTOTE/",
    "PS5 1 TB disc": "https://www.playstation.com/nl-nl/ps5/1-tb-disc/product/PSD001-PSDE01929_59-PS5CONSOLEHB2OYE/",
    "PS5 Ghost of Yotei bundle": "https://www.playstation.com/nl-nl/ps5/ghost-of-yotei-limited-edition-bundle-black/product/playstation-5-console-model-group-slim/",
    "PS5 Digital Edition 825 GB": "https://www.playstation.com/nl-nl/ps5/digital-edition-825-gb/product/PSD001-PSDE01916_79-PS5DIGITALKKBAEE/",
}

# Als een van deze teksten op de pagina staat, is het product niet beschikbaar.
SOLD_OUT_MARKERS = ["op dit moment uitverkocht", "niet beschikbaar voor aankoop"]

STATE_FILE = Path(__file__).parent / "state.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}


def check(url: str) -> str:
    """Geeft 'available', 'sold_out' of 'error' terug. Probeert tot 3 keer."""
    for attempt in range(1, 4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                text = r.text.lower()
                if any(m in text for m in SOLD_OUT_MARKERS):
                    return "sold_out"
                return "available"
            print(f"  poging {attempt}: HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"  poging {attempt}: fout: {e}")
        if attempt < 3:
            time.sleep(10)
    return "error"


def notify(topic: str, title: str, message: str, click: str | None = None, priority: str = "default"):
    headers = {"Title": title.encode("utf-8"), "Priority": priority}
    if click:
        headers["Click"] = click
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers
    )
    urllib.request.urlopen(req, timeout=30).read()


ERROR_NOTIFY_AFTER = 3  # aantal opeenvolgende mislukte runs voor een foutmelding


def main():
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        sys.exit("NTFY_TOPIC ontbreekt (zie README).")

    raw = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None
    old = None
    if raw is not None:
        # Oud formaat (alleen tekst) omzetten naar nieuw formaat.
        old = {n: v if isinstance(v, dict) else {"status": v, "errors": 0}
               for n, v in raw.items()}

    new = {}
    results = {}
    for name, url in PRODUCTS.items():
        print(f"{name}:")
        status = check(url)
        print(f"  -> {status}")
        results[name] = status

    if old is None:
        lines = [f"{n}: {s}" for n, s in results.items()]
        notify(topic, "PS5-monitor gestart", "\n".join(lines))
        new = {n: {"status": s, "errors": 1 if s == "error" else 0}
               for n, s in results.items()}
    else:
        for name, status in results.items():
            prev = old.get(name, {"status": None, "errors": 0})
            if status == "error":
                errors = prev["errors"] + 1
                new[name] = {"status": prev["status"], "errors": errors}
                if errors == ERROR_NOTIFY_AFTER:
                    notify(topic, f"{name}: pagina al {errors} keer niet te laden",
                           "De site blokkeert het script mogelijk.", priority="low")
            else:
                new[name] = {"status": status, "errors": 0}
                if status == "available" and prev["status"] != "available":
                    notify(topic, f"{name} is beschikbaar!",
                           "Snel zijn, deze zijn vaak snel weg.",
                           click=PRODUCTS[name], priority="urgent")

    STATE_FILE.write_text(json.dumps(new, indent=2) + "\n")


if __name__ == "__main__":
    main()

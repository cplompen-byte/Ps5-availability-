#!/usr/bin/env python3
"""Bewaakt PlayStation-productpagina's en stuurt een ntfy-pushmelding bij wijzigingen."""
import json
import os
import sys
import urllib.request
from pathlib import Path

import requests

PRODUCTS = {
    "PS5 Slim (refurbished)": "https://www.playstation.com/nl-nl/ps5/certified-refurbished-ps5-slim/product/PSD001-PSDE00233_59-PS5GRADEDCLIZSLE/",
    "PS5 console (refurbished)": "https://www.playstation.com/nl-nl/ps5/certified-refurbished/product/PSD001-PSDE01840_63-PS5GRADEDCEC7XZE/",
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
    """Geeft 'available', 'sold_out' of 'error' terug."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        print(f"  fout: {e}")
        return "error"
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}")
        return "error"
    text = r.text.lower()
    if any(m in text for m in SOLD_OUT_MARKERS):
        return "sold_out"
    return "available"


def notify(topic: str, title: str, message: str, click: str | None = None, priority: str = "default"):
    headers = {"Title": title.encode("utf-8"), "Priority": priority}
    if click:
        headers["Click"] = click
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers
    )
    urllib.request.urlopen(req, timeout=30).read()


def main():
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        sys.exit("NTFY_TOPIC ontbreekt (zie README).")

    old = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None
    new = {}
    for name, url in PRODUCTS.items():
        print(f"{name}:")
        status = check(url)
        print(f"  -> {status}")
        new[name] = status

    if old is None:
        # Eerste run: stuur een overzicht zodat je kunt controleren of het werkt.
        lines = [f"{n}: {s}" for n, s in new.items()]
        notify(topic, "PS5-monitor gestart", "\n".join(lines))
    else:
        for name, status in new.items():
            prev = old.get(name)
            if status == "available" and prev != "available":
                notify(topic, f"{name} is beschikbaar!", "Snel zijn, deze zijn vaak snel weg.",
                       click=PRODUCTS[name], priority="urgent")
            elif status == "error" and prev != "error":
                notify(topic, f"{name}: pagina niet te laden",
                       "De site blokkeert het script mogelijk.", priority="low")

    STATE_FILE.write_text(json.dumps(new, indent=2) + "\n")


if __name__ == "__main__":
    main()

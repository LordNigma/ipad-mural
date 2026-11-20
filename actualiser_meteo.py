#!/usr/bin/env python3
"""Construit weather.json avec Open-Meteo depuis les serveurs de GitHub Actions.
Aucune clé, aucun compte météo et aucun serveur utilisateur n'est requis.
Le JSON publié ne contient que les conditions des 4 villes (données publiques).
"""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import json
import sys

CITIES = {
    "bruxelles": (50.8503, 4.3517, "Europe/Brussels"),
    "vacoas": (-20.294079, 57.490768, "Indian/Mauritius"),
    "avellino": (40.91494, 14.79103, "Europe/Rome"),
    "flic-en-flac": (-20.27865, 57.3721538, "Indian/Mauritius"),
}

def collect(urlopen_func=urlopen):
    cities = {}
    for key, (lat, lon, tz) in CITIES.items():
        query = urlencode({
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": tz, "forecast_days": 3,
        })
        req = Request("https://api.open-meteo.com/v1/forecast?" + query,
                      headers={"User-Agent":"iPadMural/3.1.1 (personal dashboard)"})
        with urlopen_func(req, timeout=25) as r:
            content = json.load(r)
        if (content.get("error") or not isinstance(content.get("current"), dict)
                or not isinstance(content.get("daily"), dict)
                or not isinstance(content.get("utc_offset_seconds"), int)
                or not isinstance(content["current"].get("temperature_2m"),(int,float))
                or not isinstance(content["daily"].get("time"),list)):
            raise RuntimeError(f"Données Open-Meteo invalides pour {key}")
        cities[key] = content
    return {"updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "cities":cities}

if __name__=="__main__":
    dest = Path(sys.argv[1] if len(sys.argv)>1 else "weather.json")
    data = collect()
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,separators=(",", ":")),encoding="utf-8")
    temp.replace(dest)
    print(f"Météo enregistrée pour {len(data['cities'])} villes -> {dest}")

#!/usr/bin/env python3
"""Récupère UNIQUEMENT la copie AES-CCM chiffrée depuis Apps Script.
L'adresse de la web app figure dans le secret AGENDA_ENCRYPTED_URL.
Le lien iCal Google et la phrase de chiffrement ne sont jamais utilisés ici.
"""
import json
import os
import pathlib
import re
import sys
import time
import urllib.request

OUTPUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '_site/calendar.enc.json')
URL = os.environ.get('AGENDA_ENCRYPTED_URL', '').strip()
MAX_BYTES = 450_000


def is_ciphertext(blob):
    if len(blob) > MAX_BYTES:
        return False
    try:
        obj = json.loads(blob)
    except (ValueError, UnicodeDecodeError):
        return False
    if not isinstance(obj, dict):
        return False
    if obj.get('mode') != 'ccm' or obj.get('cipher') != 'aes':
        return False
    if obj.get('ks') != 256 or obj.get('ts') != 128 or obj.get('iter', 0) < 10000:
        return False
    for name in ('ct', 'iv', 'salt'):
        if not isinstance(obj.get(name), str) or not re.fullmatch(r'[A-Za-z0-9+/=_-]+', obj[name]):
            return False
    if len(obj['ct']) < 24:
        return False
    # Aucun champ contenant des événements en clair n'est accepté.
    return all(k not in obj for k in ('events', 'items', 'calendar', 'ical', 'title'))


def download(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'iPad-Mural-GitHub/3.7', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = response.read(MAX_BYTES + 1)
    if not is_ciphertext(data):
        raise ValueError('Réponse absente, invalide ou non chiffrée')
    return data


def main():
    if not URL.startswith('https://script.google.com/macros/s/'):
        print('AVERTISSEMENT agenda : AGENDA_ENCRYPTED_URL absent ou mal renseigné ; synchronisation ignorée.')
        return 0
    data = None
    for i in range(3):
        try:
            data = download(URL)
            print('Agenda Google : copie chiffrée vérifiée (aucun événement en clair).')
            break
        except Exception:
            print('Agenda Google : tentative %d/3 indisponible.' % (i + 1))
            if i < 2:
                time.sleep(2)
    if data is None:
        # La précédente copie publiée reste préférable à l'absence de calendrier.
        # URL publique connue, AUCUN secret ni authentification Google ici.
        try:
            data = download('https://lordnigma.github.io/ipad-mural/calendar.enc.json')
            print('Agenda Google : conservation de la dernière copie chiffrée publiée.')
        except Exception:
            print('Agenda Google : aucune ancienne copie disponible, rubrique en attente.')
            return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(data + (b'' if data.endswith(b'\n') else b'\n'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

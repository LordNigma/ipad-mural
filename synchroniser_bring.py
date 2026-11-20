#!/usr/bin/env python3
"""iPad Mural Bring V3.2.1: lecture seule avec journal de version non sensible.

    Pas de secrets, d'articles ou de noms de listes dans les logs.
    Compatible avec les réponses objet bring-api 1.1.2 et les anciens dict.
"""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import aiohttp
from bring_api import Bring

VERSION = 'BRING_SYNC_V3_2_1'


def valeur(obj, champ, defaut=None):
    if isinstance(obj, dict):
        return obj.get(champ, defaut)
    return getattr(obj, champ, defaut)


def uuid_de_liste(reponse, nom_demande):
    listes = valeur(reponse, 'lists')
    if not isinstance(listes, (list, tuple)):
        raise ValueError('Unexpected list response shape')
    demande = nom_demande.strip().casefold()
    correspondances = [ligne for ligne in listes
                       if str(valeur(ligne, 'name', '') or '').strip().casefold() == demande]
    if len(correspondances) != 1:
        raise LookupError('List name missing or ambiguous')
    uuid = valeur(correspondances[0], 'listUuid')
    if not isinstance(uuid, str) or not uuid:
        raise ValueError('Missing list UUID')
    return uuid


def articles_en_attente(reponse):
    groupe = valeur(reponse, 'items')
    articles = valeur(groupe, 'purchase')
    if not isinstance(articles, (list, tuple)):
        raise ValueError('Unexpected items response shape')
    resultat = []
    for element in articles:
        nom = str(valeur(element, 'itemId', '') or '').strip()
        if not nom:
            continue
        detail = str(valeur(element, 'spec', '') or '')
        resultat.append({'name': nom[:200], 'detail': detail[:250]})
    return resultat


async def recuperer():
    email = os.environ.get('BRING_EMAIL', '')
    password = os.environ.get('BRING_PASSWORD', '')
    liste_demandee = os.environ.get('BRING_LIST_NAME', '')
    if not all((email, password, liste_demandee)):
        raise RuntimeError('BRING_SECRET_MISSING')

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=35)) as session:
        bring = Bring(session, email, password)
        print('ETAPE bring_login', flush=True)
        await bring.login()
        print('OK bring_login', flush=True)

        print('ETAPE bring_load_lists', flush=True)
        reponse_listes = await bring.load_lists()
        print('OK bring_load_lists', flush=True)

        print('ETAPE bring_select_list', flush=True)
        uuid = uuid_de_liste(reponse_listes, liste_demandee)
        print('OK bring_select_list', flush=True)

        print('ETAPE bring_get_list', flush=True)
        reponse_articles = await bring.get_list(uuid)
        print('OK bring_get_list', flush=True)

        print('ETAPE bring_parse_items', flush=True)
        articles = articles_en_attente(reponse_articles)
        print('OK bring_parse_items', flush=True)

    return {
        'v': 1,
        'updated_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'items': articles,
    }


def main():
    print('VERSION ' + VERSION, flush=True)
    if len(sys.argv) != 2:
        print('ERREUR bring_args', file=sys.stderr)
        return 1
    try:
        donnees = asyncio.run(recuperer())
        sortie = Path(sys.argv[1])
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(json.dumps(donnees, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        print('OK bring_saved_for_encryption', flush=True)
        return 0
    except Exception as exc:
        # Pas de str(exc) ni de traceback : certaines exceptions peuvent contenir
        # des donnees confidentielles (URLs, noms de liste, etc.).
        print('ERREUR Bring : type=' + type(exc).__name__ + '. Consulter la derniere ETAPE affichee.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

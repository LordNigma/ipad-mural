#!/usr/bin/env python3
"""Lecture seule d'une liste Bring! ; résultat TEMPORAIRE hors du site publié.
Ne jamais logger les articles, les noms de listes ou les secrets.
"""
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import sys
import aiohttp
from bring_api import Bring

async def collect():
    email=os.environ.get("BRING_EMAIL", "")
    password=os.environ.get("BRING_PASSWORD", "")
    target=os.environ.get("BRING_LIST_NAME", "")
    if not email or not password or not target:
        raise RuntimeError("Secrets Bring! non configurés.")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=35)) as session:
        bring=Bring(session,email,password)
        await bring.login()
        print("Bring : connexion authentifiee.", flush=True)
        candidates=(await bring.load_lists())["lists"]
        print("Bring : acces aux listes confirme (noms masques).", flush=True)
        matches=[one for one in candidates if str(one.get("name","")).strip().casefold()==target.strip().casefold()]
        if len(matches)!=1:
            raise RuntimeError("Nom de liste non trouvé ou ambigu : contrôler BRING_LIST_NAME (valeur exacte).")
        print("Bring : liste selectionnee avec succes.", flush=True)
        response=await bring.get_list(matches[0]["listUuid"])
        purchase=response.items.purchase
        result=[]
        for entry in purchase:
            result.append({"name":str(entry.itemId)[:200],"detail":str(entry.spec or "")[:250]})
        return {"v":1,"updated_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),"items":result}

if __name__=="__main__":
    try:
        dest=Path(sys.argv[1])
        dest.parent.mkdir(parents=True,exist_ok=True)
        data=asyncio.run(collect())
        dest.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        print("Bring! : liste obtenue en lecture seule (détails masqués).")
    except RuntimeError as exc:
        # Messages contrôlés par notre script, ne contiennent aucun secret ni nom de liste.
        if "Nom de liste" in str(exc):
            print("ERREUR Bring : BRING_LIST_NAME ne correspond a aucune liste accessible (ou correspond a plusieurs).",file=sys.stderr)
        else:
            print("ERREUR Bring : au moins un parametre de connexion manque.",file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # Ne jamais afficher str(exc) ni de traceback: l'API peut inclure des secrets.
        print("ERREUR Bring : echec lors de l'appel a l'API. Type: " + type(exc).__name__,file=sys.stderr)
        sys.exit(1)

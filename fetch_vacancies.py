#!/usr/bin/env python3
"""Fetch public HH.ru vacancies for Kungur and Perm; classify cautiously."""
import json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
import requests

API = "https://api.hh.ru"
OUT = Path("data/vacancies.json")
HEADERS = {"User-Agent": os.getenv("HH_USER_AGENT", "RabotaRyadom/1.0 (personal vacancy search)"),
           "Accept": "application/json"}
QUERIES = ["без оформления", "без трудоустройства", "неофициально", "без ТК", "оплата наличными"]
FORMAL = re.compile(r"\b(трудов(ой|ого)\s+договор|по\s+тк|тк\s*рф|официальн(ое|ого|ое)\s+трудоустройств|гпх|самозанят|договор\s+(гпх|подряда|оказания услуг)|белая\s+зарплата)\b", re.I)
NO_PAPER = re.compile(r"(без\s+(официальн(ого|ой)\s+)?оформлен|без\s+трудоустройств|неофициальн(ое|ая|о)\s+(трудоустройств|работ)|без\s+тк\b|работа\s+без\s+договор)", re.I)
NET = re.compile(r"(на\s+руки|после\s+вычета\s+налог|чистыми|наличными|оплата\s+ежедневно)", re.I)
SHIFT = re.compile(r"(сутк|24\s*час|1\s*/\s*[123]|сутки\s+через|день\s*/\s*ночь)", re.I)
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def api_get(path, params=None):
    r = SESSION.get(API + path, params=params, timeout=25)
    r.raise_for_status()
    return r.json()

def walk_areas(nodes, wanted):
    for node in nodes:
        if node.get("name","").strip().lower() == wanted.lower():
            return str(node["id"])
        found = walk_areas(node.get("areas", []), wanted)
        if found: return found
    return None

def get_area_ids():
    tree = api_get("/areas")
    return {"Кунгур": walk_areas(tree, "Кунгур"), "Пермь": walk_areas(tree, "Пермь")}

def classify(item, detail, city):
    text = " ".join([item.get("name",""), item.get("snippet",{}).get("requirement","") or "",
                     item.get("snippet",{}).get("responsibility","") or "",
                     detail.get("description","") or "",
                     detail.get("schedule",{}).get("name","") or ""])
    schedule = detail.get("schedule",{}).get("name") or ""
    if city == "Пермь" and not SHIFT.search(text + " " + schedule):
        return None
    if FORMAL.search(text):
        return None
    no_paper = bool(NO_PAPER.search(text))
    salary = detail.get("salary") or {}
    net_by_salary = salary.get("gross") is False
    net_by_text = bool(NET.search(text))
    # Confirm only when both no-paper and take-home conditions are explicit.
    confirmed = no_paper and (net_by_salary or net_by_text)
    return {
        "id": str(item["id"]), "city": city, "title": detail.get("name") or item.get("name"),
        "company": (detail.get("employer") or {}).get("name"),
        "url": detail.get("alternate_url") or item.get("alternate_url"),
        "published_at": detail.get("published_at") or item.get("published_at"),
        "salary_from": salary.get("from"), "salary_to": salary.get("to"),
        "schedule": schedule or "График не указан",
        "description": re.sub(r"<[^>]+>", " ", detail.get("description") or ""),
        "status": "confirmed" if confirmed else "review",
        "net_confirmed": bool(net_by_salary or net_by_text),
        "no_paper_confirmed": no_paper
    }

def main():
    OUT.parent.mkdir(exist_ok=True)
    area_ids = get_area_ids()
    all_found = {}
    errors = []
    for city, area in area_ids.items():
        if not area:
            errors.append(f"Не найден идентификатор региона: {city}")
            continue
        for query in QUERIES:
            try:
                data = api_get("/vacancies", {"area": area, "text": query, "per_page": 50,
                                              "order_by": "publication_time", "period": 7})
                for item in data.get("items", []):
                    vid = str(item["id"])
                    if vid in all_found: continue
                    try:
                        detail = api_get("/vacancies/" + vid)
                        classified = classify(item, detail, city)
                        if classified: all_found[vid] = classified
                    except Exception as exc:
                        errors.append(f"Вакансия {vid}: {exc}")
                    time.sleep(0.25)
                time.sleep(0.5)
            except Exception as exc:
                errors.append(f"{city}/{query}: {exc}")
    old = {}
    if OUT.exists():
        try: old = {str(x["id"]): x for x in json.loads(OUT.read_text("utf-8")).get("vacancies", [])}
        except Exception: pass
    # Preserve old entries for up to 30 days if a transient API error omits them.
    cutoff = datetime.now(timezone.utc).timestamp() - 30*86400
    for vid, v in old.items():
        try:
            if vid not in all_found and datetime.fromisoformat((v.get("published_at") or "").replace("Z","+00:00")).timestamp() > cutoff:
                all_found[vid] = v
        except Exception: pass
    vacancies = sorted(all_found.values(), key=lambda x: x.get("published_at") or "", reverse=True)
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "source": "HH.ru public API",
               "cities": area_ids, "errors": errors[:30], "vacancies": vacancies}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(vacancies)} vacancies; errors={len(errors)}; areas={area_ids}")

if __name__ == "__main__":
    main()

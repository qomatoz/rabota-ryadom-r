import json, re, hashlib
from datetime import datetime, timezone
from pathlib import Path
from sources import collect

OUT = Path("data/vacancies.json")
FORMAL = re.compile(r"трудов(ой|ого) договор|по тк\b|тк рф|гпх|самозанят|официальн(ое|ого) трудоустройств|оформлени[ея] по трудов", re.I)
NO_PAPER = re.compile(r"без (официального )?оформлен|без трудоустройств|неофициальн(ое|ая|о) трудоустройств|без тк\b|без договор", re.I)
NET = re.compile(r"на руки|чистыми|наличными|ежедневн[а-я]* оплат", re.I)
SHIFT = re.compile(r"сутк|24\s*час|1\s*/\s*[123]|день\s*/\s*ночь", re.I)

def classify(v):
    text = " ".join(str(v.get(k) or "") for k in ("title","company","description","raw_text","schedule"))
    if FORMAL.search(text): return None
    if v["city"] == "Пермь" and not SHIFT.search(text): return None
    a, b = bool(NO_PAPER.search(text)), bool(NET.search(text))
    v["status"] = "confirmed" if a and b else "review"
    v["no_paper_confirmed"], v["net_confirmed"] = a, b
    v.pop("raw_text", None)
    v["id"] = v.get("id") or hashlib.sha1(str(v.get("url") or v.get("title")).encode()).hexdigest()[:18]
    return v

def main():
    rows, errors = collect(["Кунгур","Пермь"])
    merged = {}
    for v in rows:
        key = str(v.get("url") or v.get("id")).split("?")[0].rstrip("/")
        if key not in merged or len(v.get("description","")) > len(merged[key].get("description","")):
            merged[key] = v
    vacancies = [x for v in merged.values() if (x := classify(v))]
    vacancies.sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)
    counts = {}
    for v in vacancies: counts[v.get("source","Другой")] = counts.get(v.get("source","Другой"),0)+1
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),
      "source":"Мульти-источниковый поиск","cities":{"Кунгур":"любой график","Пермь":"только суточные смены"},
      "source_counts":counts,"errors":errors,"vacancies":vacancies},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Вакансий:",len(vacancies),"Источники:",counts,"Предупреждений:",len(errors))
if __name__ == "__main__": main()

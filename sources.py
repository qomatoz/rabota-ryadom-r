import os, re, time, hashlib
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime
import requests
from bs4 import BeautifulSoup

S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (compatible; RabotaRyadom/1.0)","Accept-Language":"ru-RU,ru;q=0.9"})
def clean(x):
    return re.sub(r"\s+"," ",BeautifulSoup(str(x or ""),"html.parser").get_text(" ",strip=True)).strip()
def uid(x): return hashlib.sha1(x.encode()).hexdigest()[:18]
def bing(q,city,source):
    u="https://www.bing.com/search?format=rss&count=20&q="+quote_plus(q+" "+city)
    r=S.get(u,timeout=25); r.raise_for_status()
    root=ET.fromstring(r.content); out=[]
    for n in root.findall(".//item")[:15]:
        title=clean(n.findtext("title")); link=(n.findtext("link") or "").strip(); desc=clean(n.findtext("description"))
        if not title or not link: continue
        out.append({"id":"web-"+uid(link),"city":city,"title":title,"company":source+" · публичный поиск",
          "url":link,"published_at":n.findtext("pubDate"),"salary_from":None,"salary_to":None,
          "schedule":"График уточнить","description":desc,"source":source,"raw_text":title+" "+desc})
    return out
def indexed(city):
    out=[]; errors=[]
    for source,q in [("Avito",'site:avito.ru "работа" OR "подработка" OR "вакансия'),
                     ("Telegram",'site:t.me/s/ "работа" OR "вакансия" OR "подработка"'),
                     ("ВКонтакте",'site:vk.com/wall "работа" OR "вакансия" OR "подработка"')]:
        try: out += bing(q,city,source)
        except Exception as e: errors.append(source+" индекс: "+str(e)[:160])
        time.sleep(1)
    return out,errors
def superjob(city):
    key=os.getenv("SUPERJOB_APP_ID","").strip()
    if not key: return [],["SuperJob: добавь SUPERJOB_APP_ID в GitHub Secrets"]
    out=[]; errors=[]
    for term in ["работа","подработка","без оформления","ежедневная оплата","сутки"]:
        try:
            r=S.get("https://api.superjob.ru/2.0/vacancies/",params={"keyword":term+" "+city,"count":100,"page":0},
                    headers={"X-Api-App-Id":key},timeout=25); r.raise_for_status()
            for v in r.json().get("objects",[]):
                town=clean((v.get("town") or {}).get("title")); addr=clean(v.get("address"))
                body=clean(v.get("work")); title=clean(v.get("profession")) or "Вакансия"
                if city.lower() not in (town+" "+addr+" "+title+" "+body).lower() and not (city=="Пермь" and "пермск" in body.lower()): continue
                d=v.get("date_published")
                out.append({"id":"sj-"+str(v.get("id")),"city":city,"title":title,"company":clean(v.get("firm_name")),
                  "url":v.get("link") or "https://www.superjob.ru/vakansii/","published_at":time.strftime("%Y-%m-%dT%H:%M:%S+00:00",time.gmtime(d)) if d else None,
                  "salary_from":v.get("payment_from") or None,"salary_to":v.get("payment_to") or None,
                  "schedule":clean((v.get("type_of_work") or {}).get("title")),"description":body,"source":"SuperJob","raw_text":town+" "+addr+" "+body})
        except Exception as e: errors.append("SuperJob/"+term+": "+str(e)[:160])
        time.sleep(.3)
    return out,errors
def vk(city):
    token=os.getenv("VK_ACCESS_TOKEN","").strip()
    if not token: return [],["VK API: добавь VK_ACCESS_TOKEN в GitHub Secrets; публичный индекс ищется отдельно"]
    out=[]; errors=[]
    for term in ["работа","подработка","без оформления","ежедневная оплата","сутки"]:
        try:
            r=S.get("https://api.vk.com/method/newsfeed.search.json",params={"q":term+" "+city,"count":50,"access_token":token,"v":"5.199"},timeout=25)
            r.raise_for_status(); data=r.json()
            if data.get("error"): raise RuntimeError(data["error"].get("error_msg","VK API error"))
            for p in data.get("response",{}).get("items",[]):
                body=clean(p.get("text"))
                if not body: continue
                owner,pid=p.get("owner_id"),p.get("id"); d=p.get("date")
                out.append({"id":f"vk-{owner}-{pid}","city":city,"title":body[:100],"company":"ВКонтакте",
                  "url":f"https://vk.com/wall{owner}_{pid}","published_at":time.strftime("%Y-%m-%dT%H:%M:%S+00:00",time.gmtime(d)) if d else None,
                  "salary_from":None,"salary_to":None,"schedule":"График уточнить","description":body,"source":"ВКонтакте","raw_text":body})
        except Exception as e: errors.append("VK/"+term+": "+str(e)[:160])
        time.sleep(.3)
    return out,errors
def telegram(city):
    channels=[x.strip().lstrip("@") for x in os.getenv("TELEGRAM_CHANNELS","").split(",") if x.strip()]
    out=[]; errors=[]
    for ch in channels[:40]:
        try:
            r=S.get("https://t.me/s/"+ch,timeout=25); r.raise_for_status(); soup=BeautifulSoup(r.text,"html.parser")
            for m in soup.select(".tgme_widget_message")[-40:]:
                body=clean(m.select_one(".tgme_widget_message_text"))
                if not body or city.lower() not in body.lower() and not (city=="Пермь" and "пермск" in body.lower()): continue
                t=m.select_one("time"); a=m.select_one(".tgme_widget_message_date"); link=a.get("href") if a else "https://t.me/"+ch
                out.append({"id":"tg-"+uid(link),"city":city,"title":body[:100],"company":"Telegram @"+ch,
                  "url":link,"published_at":t.get("datetime") if t else None,"salary_from":None,"salary_to":None,
                  "schedule":"График уточнить","description":body,"source":"Telegram","raw_text":body})
        except Exception as e: errors.append("Telegram @"+ch+": "+str(e)[:160])
    if not channels: errors.append("Telegram: задай публичные каналы в переменной TELEGRAM_CHANNELS (имена через запятую)")
    return out,errors
def collect(cities):
    out=[]; errors=[]
    for city in cities:
        for fn in (indexed,superjob,vk,telegram):
            a,b=fn(city); out+=a; errors += [city+"/"+x for x in b]
    return out,errors

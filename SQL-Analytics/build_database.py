# -*- coding: utf-8 -*-
"""
Rebuild bpo_analytics.db from schema.sql and generate synthetic BPO sample data.
Portable: run from anywhere with `python build_database.py` (uses this file's folder).
No third-party libraries — standard library only.
"""
import sqlite3, random, os
from datetime import date, timedelta

random.seed(2026)
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "bpo_analytics.db")
TODAY = date(2026, 8, 8)

FIRST = ["Thabo","Lerato","Sipho","Naledi","Kagiso","Zanele","Tumelo","Ayanda","Bongani","Nomvula",
         "Kabelo","Refilwe","Mpho","Lindiwe","Sibusiso","Palesa","Katlego","Nonhlanhla","Themba","Dineo",
         "Musa","Precious","Andile","Boitumelo","Lwazi","Zodwa","Tshepo","Amahle","Sanele","Nokuthula",
         "Karabo","Anele","Wandile","Rethabile","Onalenna","Keabetswe","Tebogo","Gift","Portia","Neo"]
LAST = ["Mokoena","Nkosi","Dlamini","Molefe","Khumalo","Mahlangu","Sithole","Ndlovu","Mabaso","Zulu",
        "Ngcobo","Radebe","Mthembu","Tshabalala","Maseko","Cele","Buthelezi","Naidoo","Pillay","Botha"]
CAMPAIGNS = [
    ("Vodacom Upgrades","Vodacom","Sales"), ("ABSA Collections","ABSA","Collections"),
    ("MTN Retentions","MTN","Retentions"), ("Takealot Care","Takealot","Customer Care"),
    ("Telkom Tech Support","Telkom","Tech Support"), ("Nedbank Debt Review","Nedbank","Collections"),
    ("DStv Upsell","MultiChoice","Sales"), ("Discovery Lead Gen","Discovery","Lead Gen"),
    ("Standard Bank Helpdesk","Standard Bank","Customer Care"), ("OUTsurance Sales","OUTsurance","Sales"),
]

if os.path.exists(DB):
    os.remove(DB)
conn = sqlite3.connect(DB)
cur = conn.cursor()
with open(os.path.join(HERE, "schema.sql"), encoding="utf-8") as f:
    cur.executescript(f.read())

for i, (nm, client, typ) in enumerate(CAMPAIGNS, start=1):
    cur.execute("INSERT INTO campaigns VALUES (?,?,?,?)", (i, nm, client, typ))

agents, aid = [], 1000
for cid in range(1, len(CAMPAIGNS) + 1):
    for _ in range(random.randint(9, 16)):
        aid += 1
        gender = random.choices(["Female", "Male"], weights=[58, 42])[0]
        days_ago = int(random.triangular(20, 1400, 240))
        hire = TODAY - timedelta(days=days_ago)
        resigned = random.random() < (0.28 if days_ago < 240 else 0.12)
        if resigned:
            exitd = hire + timedelta(days=random.randint(25, max(26, (TODAY - hire).days)))
            exitd = min(exitd, TODAY)
            status, exit_s, active = "Resigned", exitd.isoformat(), False
        else:
            status, exit_s, active = "Active", None, True
        cur.execute("INSERT INTO agents VALUES (?,?,?,?,?,?,?,?,?)",
                    (aid, f"{random.choice(FIRST)} {random.choice(LAST)}", gender,
                     random.choice(["Alpha", "Bravo", "Charlie"]), cid, hire.isoformat(),
                     status, exit_s, random.choice([14000, 16000, 18500, 21000, 24000, 28000])))
        agents.append((aid, cid, active))

active_by_camp = {}
for a_id, cid, active in agents:
    if active:
        active_by_camp.setdefault(cid, []).append(a_id)

sales_types = {"Sales", "Lead Gen", "Retentions"}
camp_type = {i + 1: CAMPAIGNS[i][2] for i in range(len(CAMPAIGNS))}
call_id, rows, d0 = 0, [], date(2026, 6, 1)
for day_off in range(61):
    d = d0 + timedelta(days=day_off)
    vol_factor = 0.5 if d.weekday() >= 5 else 1.0
    for cid in range(1, len(CAMPAIGNS) + 1):
        pool = active_by_camp.get(cid, [])
        if not pool:
            continue
        for _ in range(int(len(pool) * random.randint(6, 11) * vol_factor)):
            call_id += 1
            if random.random() < 0.07:   # abandoned in queue
                rows.append((call_id, cid, None, d.isoformat(), 0, random.randint(1, 120), 0, None, None, 0))
            else:
                sale = 0
                if camp_type[cid] in sales_types and random.random() < 0.16:
                    sale = round(random.choice([199, 299, 499, 599, 899, 1299]) * random.uniform(1, 1.5), 2)
                rows.append((call_id, cid, random.choice(pool), d.isoformat(),
                             random.randint(120, 520), random.randint(1, 60), 1,
                             random.choices([None, 1, 2, 3, 4, 5], weights=[58, 3, 5, 10, 12, 12])[0],
                             random.choices([1, 0], weights=[85, 15])[0], sale))

cur.executemany("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
conn.commit()
conn.close()
print(f"Built {DB}\n  {len(CAMPAIGNS)} campaigns, {len(agents)} agents, {len(rows):,} calls")

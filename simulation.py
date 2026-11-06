"""LunaOS simulation engine. Pure Python: no Streamlit imports.

Units: oxygen kg, water L, food kg, battery kWh. Shielding, structure, dust and
crew health are 0-100 conditions. Numbers marked GAME are simplified assumptions;
see data/events.py (SCIENCE) for what is research-based.
"""
import random
from data.events import EVENTS, SCRIPTED
from data.voice import WARN, DECISION_GOOD, DECISION_BAD

DAYS = 30
CONS = ("oxygen", "water", "food", "energy")
DIFFICULTY = {"Cadet": dict(m=.85, ev=.35, cr=320),
              "Engineer": dict(m=1.0, ev=.5, cr=240),
              "Commander": dict(m=1.2, ev=.65, cr=180)}
PER_PERSON = dict(oxygen=.84, water=3.5, food=.62)      # per day, approximate
STOCK_DAYS = dict(oxygen=12, water=14, food=28)         # GAME: starting stock
BATTERY_KWH, ARRAY_KW = 600, 6                          # GAME
UP_NAMES = {"life": "Life support", "power": "Power", "agri": "Agriculture", "protect": "Protection"}
DEFAULTS = dict(o2_recycle=80, water_recycle=80, farm=50, science=40, maint=40)


def sun_fraction(day):
    """GAME lighting profile: full sun, dusk, long night, dawn."""
    return 1.0 if day <= 12 else .5 if day <= 15 else .25 if day <= 26 else .6


def sun_label(day):
    return "Daylight" if day <= 12 else "Dusk" if day <= 15 else "Lunar night" if day <= 26 else "Dawn"


def fresh_mission(crew=4, difficulty="Engineer"):
    caps = {k: crew * PER_PERSON[k] * STOCK_DAYS[k] for k in PER_PERSON}
    m = dict(started=False, over=False, won=False, reason="", day=1, crew=crew, alive=crew,
             difficulty=difficulty, credits=DIFFICULTY[difficulty]["cr"], caps=caps,
             res=dict(caps), shielding=100., structure=100., hp=100., dust=0., dose=0.,
             battery_health=1., faults={"oxygen_leak": False, "water_leak": False},
             settings=dict(DEFAULTS), upgrades={k: 0 for k in UP_NAMES}, event=None,
             last_event=None, log=[], history=[], decisions=[], lost=0,
             issues={"Life support": 0, "Power": 0, "Agriculture": 0, "Protection": 0})
    m["res"]["energy"] = cap(m, "energy")
    return m


def cap(m, k):
    if k == "energy":
        return BATTERY_KWH * m["battery_health"] * (1 + .1 * m["upgrades"]["power"])
    return m["caps"][k]


def pct(m, k):
    return 100 * m["res"][k] / cap(m, k)


def log(m, kind, msg):
    m["log"].insert(0, dict(day=m["day"], type=kind, msg=msg))


def project(m, s=None, day=None):
    """Expected change for one day with the given settings (no random events)."""
    s, day = s or m["settings"], day or m["day"]
    dm, n, up = DIFFICULTY[m["difficulty"]]["m"], m["alive"], m["upgrades"]
    ro = min(s["o2_recycle"] / 100, .85 + .03 * up["life"])
    rw = min(s["water_recycle"] / 100, .90 + .02 * up["life"])
    use = {k: n * PER_PERSON[k] * dm for k in PER_PERSON}
    rec_o, rec_w = use["oxygen"] * ro, use["water"] * rw
    farm = s["farm"] / 100
    food_made = farm * n * PER_PERSON["food"] * .8 * (1 + .15 * up["agri"])
    leak_o = .04 * m["caps"]["oxygen"] if m["faults"]["oxygen_leak"] else 0
    leak_w = .04 * m["caps"]["water"] if m["faults"]["water_leak"] else 0
    loads = dict(habitat=24 + 5 * n, recycling=3 * rec_o + .5 * rec_w,
                 greenhouse=.3 * s["farm"] * n / 4, science=.2 * s["science"])
    load = sum(loads.values())
    gen = ARRAY_KW * 24 * sun_fraction(day) * (1 + .12 * up["power"]) * (1 - m["dust"] / 150)
    net = gen - load
    d = dict(oxygen=-(use["oxygen"] - rec_o) - leak_o,
             water=-(use["water"] - rec_w) - farm * n - leak_w,
             food=food_made - use["food"],
             energy=net * .9 if net > 0 else net)
    return dict(d=d, gen=gen, load=load, loads=loads, net=net, dm=dm,
                parts=dict(use=use, rec_o=rec_o, rec_w=rec_w, food_made=food_made, farm_water=farm * n,
                           leak_o=leak_o, leak_w=leak_w, farm=s["farm"], n=n),
                shielding=-.6 * dm * (1 - .15 * up["protect"]) + .012 * s["maint"] * (1 + .1 * up["protect"]),
                structure=-.3 * dm + .006 * s["maint"],
                dose=.5 + 4 * (1 - m["shielding"] / 100),
                credits=12 + .4 * loads["science"] - .06 * s["maint"])


def forecast_energy(m, s=None):
    """Project battery % through day 30 using current dust and settings (events ignored)."""
    e, c, out, dust = m["res"]["energy"], cap(m, "energy"), [], m["dust"]
    for day in range(m["day"], DAYS + 1):
        tmp = dict(m, dust=dust)
        e = min(c, max(0, e + project(tmp, s, day)["d"]["energy"]))
        out.append((day, 100 * e / c))
        dust = min(100, dust + 1.5)
    return out


def advance_day(m):
    if m["over"] or m["event"] or not m["started"]:
        return False
    p = project(m)
    for k in CONS:
        m["res"][k] = min(cap(m, k), max(0, m["res"][k] + p["d"][k]))
    m["shielding"] = min(100, max(0, m["shielding"] + p["shielding"]))
    m["structure"] = min(100, max(0, m["structure"] + p["structure"]))
    m["dose"] += p["dose"]
    m["credits"] = max(0, m["credits"] + p["credits"])
    m["dust"] = min(100, m["dust"] + 1.5)
    dmg = 0
    for k, sysname, w in (("oxygen", "Life support", 10), ("water", "Life support", 8), ("food", "Agriculture", 8)):
        if pct(m, k) < 15:
            dmg += w; m["issues"][sysname] += 1
            log(m, "WARN", WARN[k])
    if pct(m, "energy") < 15:
        dmg += 5; m["issues"]["Power"] += 1; log(m, "WARN", WARN["energy"])
    if m["shielding"] < 30:
        m["issues"]["Protection"] += 1; log(m, "WARN", WARN["shielding"])
    dmg += max(0, p["dose"] - 2) * 1.5
    m["hp"] = m["hp"] - dmg if dmg else min(100, m["hp"] + 4)
    if m["hp"] <= 0:
        m["alive"] -= 1; m["lost"] += 1; m["hp"] = 50
        log(m, "CREW", "A crew member was lost.")
    m["history"].append(dict(day=m["day"], **{k: pct(m, k) for k in CONS}, shielding=m["shielding"],
                             structure=m["structure"], gen=p["gen"], load=p["load"], dust=m["dust"],
                             hp=m["hp"], credits=m["credits"], science=m["settings"]["science"],
                             farm=m["settings"]["farm"], maint=m["settings"]["maint"]))
    log(m, "TURN", f"Day {m['day']} done. Generated {p['gen']:.0f} kWh, used {p['load']:.0f} kWh.")
    _check(m)
    if not m["over"]:
        if m["day"] >= DAYS:
            _end(m, True, "Mission completed. All 30 days survived.")
        else:
            m["day"] += 1
            roll_event(m)
    return True


def _check(m):
    for k in CONS:
        if m["res"][k] <= 0:
            return _end(m, False, f"{k.title() if k != 'energy' else 'Battery'} reached 0%.")
    if m["structure"] <= 0:
        return _end(m, False, "Structural integrity reached 0%.")
    if m["alive"] <= 0:
        return _end(m, False, "All crew members were lost.")


def _end(m, won, reason):
    m["over"], m["won"], m["reason"] = True, won, reason
    log(m, "END", reason)


def roll_event(m):
    eid = SCRIPTED.get(m["day"])
    if not eid and random.random() < DIFFICULTY[m["difficulty"]]["ev"]:
        eid = random.choice([e for e in EVENTS if e != m["last_event"]])
    if eid:
        m["event"] = m["last_event"] = eid
        log(m, "EVENT", f"{EVENTS[eid]['title']}: response required.")


def apply_fx(m, fx):
    impact = 0
    for k, v in fx.items():
        if k in CONS:
            before = m["res"][k]
            m["res"][k] = min(cap(m, k), max(0, before + cap(m, k) * v / 100))
            impact += abs(v)
        elif k in ("shielding", "structure"):
            m[k] = min(100, max(0, m[k] + v)); impact += abs(v)
        elif k == "hp":
            m["hp"] = max(1, m["hp"] + v); impact += abs(v)
        elif k in ("dust", "dose", "credits", "battery_health"):
            if k == "battery_health":
                m[k] = max(.3, m[k] + v)
                m["res"]["energy"] = min(m["res"]["energy"], cap(m, "energy"))
            elif k == "credits":
                m["credits"] += v
            elif k == "dust":
                m["dust"] = min(100, max(0, m["dust"] + v))
            else:
                m["dose"] += v
        elif k == "fault":
            m["faults"][v] = True
    return impact


def resolve_event(m, i):
    ev = EVENTS[m["event"]]
    c = ev["choices"][i]
    if c["cost"] > m["credits"]:
        return False
    m["credits"] -= c["cost"]
    impact = apply_fx(m, c["fx"])
    log(m, "DECISION", f"{ev['title']}: {c['label']}")
    log(m, "FEEDBACK", DECISION_GOOD if impact <= 8 else DECISION_BAD)
    if c.get("risk") and random.random() < c["risk"]["p"]:
        apply_fx(m, c["risk"]["fx"])
        log(m, "RISK", "The fix failed and a lasting leak has started. Repair it in Systems & Engineering.")
    if ev["system"]:
        m["issues"][ev["system"]] += 1
    m["decisions"].append(dict(day=m["day"], event=ev["title"], choice=c["label"], impact=impact, cost=c["cost"]))
    m["event"] = None
    _check(m)
    return True


def upgrade_cost(m, key):
    return 60 * (m["upgrades"][key] + 1)


def upgrade(m, key):
    cost = upgrade_cost(m, key)
    if m["upgrades"][key] >= 5 or m["credits"] < cost:
        return False
    m["credits"] -= cost; m["upgrades"][key] += 1
    log(m, "UPGRADE", f"{UP_NAMES[key]} upgraded to level {m['upgrades'][key]} (-{cost} cr)")
    return True


def clean_panels(m):
    if m["credits"] < 20:
        return False
    m["credits"] -= 20; m["dust"] = max(0, m["dust"] - 30)
    log(m, "REPAIR", "Panels cleaned: dust -30% (-20 cr)")
    return True


def repair_fault(m, name):
    if m["credits"] < 30 or not m["faults"][name]:
        return False
    m["credits"] -= 30; m["faults"][name] = False
    log(m, "REPAIR", f"{name.replace('_', ' ').title()} repaired (-30 cr)")
    return True


def emergency_repair(m):
    if m["credits"] < 40:
        return False
    m["credits"] -= 40
    m["structure"] = min(100, m["structure"] + 20); m["shielding"] = min(100, m["shielding"] + 15)
    log(m, "REPAIR", "Emergency repair: structure +20, shielding +15 (-40 cr)")
    return True


def analyse(m):
    H = m["history"]
    if not H:
        return None
    lowest = {k: min((h[k], h["day"]) for h in H) for k in CONS}
    worst_res = min(lowest, key=lambda k: lowest[k][0])
    prep = next((h["energy"] for h in H if h["day"] == 15), None)
    worst_sys = max(m["issues"], key=m["issues"].get)
    return dict(lowest=lowest, worst_res=worst_res, gen=sum(h["gen"] for h in H),
                load=sum(h["load"] for h in H), night_prep=prep, worst_sys=worst_sys,
                top_decisions=sorted(m["decisions"], key=lambda d: -d["impact"])[:3],
                score=round(sum(pct(m, k) for k in CONS) / 4 * (1 if m["won"] else .4) + m["alive"] * 5))
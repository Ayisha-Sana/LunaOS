"""LunaOS voice: commander briefings, microcopy, explainers and debrief text.
Pure text helpers. Functions that need engine data take the simulation module as an argument."""

WARN = {
 "oxygen": "LIFE SUPPORT ALERT: oxygen is critically low. The crew can feel it.",
 "water": "LIFE SUPPORT ALERT: water is critically low. Health is declining.",
 "food": "AGRICULTURE NOTICE: food reserves are critical. Your greenhouse is not keeping up.",
 "energy": "POWER RESERVE CRITICAL: you're running on borrowed sunlight.",
 "shielding": "SHIELDING LOW: radiation exposure is climbing.",
}
DECISION_GOOD = "Nice call, Commander. The habitat gained breathing room."
DECISION_BAD = "That decision has consequences. Welcome to mission planning."
NAMES = {"oxygen": "Oxygen", "water": "Water", "food": "Food", "energy": "Battery",
         "shielding": "Shielding", "structure": "Structure"}


def system_status(m, sim):
    v = min([sim.pct(m, k) for k in sim.CONS] + [m["shielding"], m["structure"]])
    return "NOMINAL" if v > 50 else "CAUTION" if v > 25 else "CRITICAL"


def commander_briefing(m, sim):
    day = m["day"]
    fc = sim.forecast_energy(m)
    dead = next((d for d, v in fc if v <= 0), None)
    if day < 16:
        night = f"Lunar night begins in {16 - day} day{'s' if 16 - day != 1 else ''}."
    elif day <= 26:
        night = f"Lunar night is underway. Dawn is {27 - day} days away."
    else:
        night = "Dawn has returned."
    if dead:
        body = (f"At the current load your battery reserves last until day {dead}, "
                f"about **{dead - day} days**. \n\n**Recommendation:** shed load or build reserves before nightfall.")
    else:
        d, low = min(fc, key=lambda x: x[1])
        body = (f"Your battery should hold, bottoming out near **{low:.0f}%** on day {d}. "
                "\n\n**Recommendation:** watch panel dust and be ready for incidents.")
    ev = "\n\n**Incident pending.** Check the Mission Feed." if m["event"] else ""
    return f"**GOOD MORNING, COMMANDER.**  \n{night}\n\n{body}{ev}"


def explain(m, k, p):
    pr, d = p["parts"], p["d"]
    n = pr["n"]
    if k == "oxygen":
        t = (f"Your {n} crew breathed {pr['use']['oxygen']:.1f} kg of oxygen. Recyclers recovered {pr['rec_o']:.1f} kg. "
             f"{'A leak also vented ' + format(pr['leak_o'], '.1f') + ' kg. ' if pr['leak_o'] else ''}Net change: {d['oxygen']:+.1f} kg.")
        r = "Stations generate oxygen by electrolysis and recover more from CO2, but both steps need electricity."
    elif k == "water":
        t = (f"The crew used {pr['use']['water']:.1f} L and recyclers returned {pr['rec_w']:.1f} L. The greenhouse took {pr['farm_water']:.1f} L. "
             f"{'A leak lost ' + format(pr['leak_w'], '.1f') + ' L. ' if pr['leak_w'] else ''}Net change: {d['water']:+.1f} L.")
        r = "Water recovery is what makes long missions possible. Every litre recycled is a litre you never launch."
    elif k == "food":
        t = (f"The crew ate {pr['use']['food']:.2f} kg. Your greenhouse, at {pr['farm']}% output, produced {pr['food_made']:.2f} kg. "
             f"Net change: {d['food']:+.2f} kg.")
        r = "A lunar habitat must balance food production against the power and water the growing system consumes."
    elif k == "energy":
        t = (f"Generation was {p['gen']:.0f} kWh ({sim_label(m)}, {m['dust']:.0f}% dust) against {p['load']:.0f} kWh of load. "
             f"Net change in the battery: {d['energy']:+.0f} kWh.")
        r = "At the lunar poles the Sun sits very low, so panel placement, dust and long dark periods drive storage design."
    elif k == "shielding":
        t = f"Shielding wears down by itself and maintenance rebuilds it. Today's net change is {p['shielding']:+.2f} points."
        r = "Regolith and structure absorb radiation. Protection is a condition that must be maintained, not a stock you spend."
    else:
        t = f"Structure slowly degrades and maintenance offsets it. Today's net change is {p['structure']:+.2f} points."
        r = "Habitat hulls face thermal cycling and micrometeoroids, so inspection and repair are continuous jobs."
    return f"{t}\n\n**Real-world connection:** {r}"


def sim_label(m):
    d = m["day"]
    return "daylight" if d <= 12 else "dusk" if d <= 15 else "lunar night" if d <= 26 else "dawn"


def command_style(m):
    H = m["history"]
    if not H:
        return "UNTESTED COMMANDER", "The mission ended before your style could show."
    avg = lambda k: sum(h[k] for h in H) / len(H)
    sci, farm, maint, emin = avg("science"), avg("farm"), avg("maint"), min(h["energy"] for h in H)
    if sci >= 55:
        return "RESEARCH PIONEER", "You pushed science output hard and accepted thinner power margins to get it."
    if maint >= 60:
        return "HABITAT GUARDIAN", "You invested heavily in maintenance, keeping the shell and shielding healthy."
    if farm >= 65:
        return "GREENHOUSE GARDENER", "You leaned on hydroponics for food and paid for it in water and power."
    if sci <= 25 and emin >= 35:
        return "RESOURCE CONSERVATOR", "You prioritized maintaining reserves over maximizing scientific output."
    return "BALANCED OPERATOR", "You spread your effort across every subsystem instead of maximizing one."


def taught(A, m):
    cover = A["gen"] / max(A["load"], 1) * 100
    return (f"Lunar missions aren't simply about having *enough* resources. They're about deciding **which resources deserve power, when, and why.** "
            f"Over your mission the array covered {cover:.0f}% of demand, and your worst subsystem was {A['worst_sys']}.")
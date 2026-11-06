import time
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import simulation as sim
from data import voice
from data.events import EVENTS, SCIENCE, describe

st.set_page_config(page_title="LunaOS", page_icon="🌙", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'IBM Plex Mono',monospace}
h1,h2,h3{font-family:'Chakra Petch',sans-serif!important;letter-spacing:.02em}
h1{color:#22d3ee}
.stApp{background:radial-gradient(ellipse at 85% -10%,#12204a 0%,#060d1f 55%)}
.hdr{font-size:11px;letter-spacing:.14em;color:#8aa0c4;border-bottom:1px solid #17305a;padding-bottom:6px;margin-bottom:6px}
[data-testid="stMetric"],[data-testid="stExpander"]{border-radius:10px}
[data-testid="stSidebar"]{background:#040a18;border-right:1px solid #17305a}
[data-testid="stMetric"]{background:#0b1630;border:1px solid #17305a;border-radius:6px;padding:10px 14px}
.stButton>button[kind="primary"]{background:#22d3ee;color:#060d1f;border:0;font-weight:600}
</style>""", unsafe_allow_html=True)

PAGES = ["Initialize", "Command Deck", "Habitat", "Mission Feed", "Post-Mission"]
HELP = {"oxygen": ("Oxygen", "kg", "Breathable oxygen in storage."),
        "water": ("Water", "L", "Usable water in storage."),
        "food": ("Food", "kg", "Food reserves (dry mass)."),
        "energy": ("Battery", "kWh", "Stored electrical energy.")}
ss = st.session_state
if "m" not in ss:
    ss.m = sim.fresh_mission()
    ss.page = PAGES[0]
for k, v in sim.DEFAULTS.items():
    ss.setdefault("w_" + k, v)
m = ss.m


# ---------- callbacks ----------
def goto(page):
    ss.page = page


def start():
    ss.m = sim.fresh_mission(ss.crew_sel, ss.diff_sel)
    ss.m["started"] = True
    sim.log(ss.m, "START", f"Mission initialised: {ss.crew_sel} crew, {ss.diff_sel}.")
    for k, v in sim.DEFAULTS.items():
        ss["w_" + k] = v
    ss.boot = True
    ss.page = "Command Deck"


def advance():
    if ss.m["event"]:
        ss.flash = "Resolve the active event in Mission Feed first."
        return
    sim.advance_day(ss.m)
    if ss.m["over"]:
        ss.page = "Post-Mission"


def apply_settings():
    ss.m["settings"] = {k: ss["w_" + k] for k in sim.DEFAULTS}
    sim.log(ss.m, "SETTINGS", "Systems settings updated.")


def act(fn, *a):
    fn(ss.m, *a)
    if ss.m["over"]:
        ss.page = "Post-Mission"


def finish_boot():
    ss.boot = False


def new_mission():
    ss.m = sim.fresh_mission()
    ss.page = PAGES[0]


# ---------- sidebar and locking ----------
locked = {"Command Deck": not m["started"], "Habitat": not m["started"],
          "Mission Feed": not m["started"], "Post-Mission": not m["over"]}
with st.sidebar:
    st.markdown("## LUNAOS\n<small>HABITAT OPERATING SYSTEM</small>", unsafe_allow_html=True)
    st.radio("Navigation", PAGES, key="page")
    if m["started"]:
        st.caption(f"MISSION DAY {m['day']:02d} // {sim.DAYS}  \nSYSTEM STATUS: {voice.system_status(m, sim)}")
        if m["event"]:
            st.warning("Active event")
page = ss.page
if locked.get(page):
    st.warning("This page is locked. " + ("Initialise the mission first." if page != "Post-Mission"
                                          else "It unlocks when the mission ends."))
    st.stop()
if ss.get("flash"):
    st.warning(ss.pop("flash"))


def header(title):
    if m["started"]:
        st.markdown(f"<div class='hdr'>LUNAOS // HABITAT OPERATING SYSTEM &nbsp;|&nbsp; MISSION DAY {m['day']:02d} // {sim.DAYS} &nbsp;|&nbsp; SYSTEM STATUS: {voice.system_status(m, sim)}</div>", unsafe_allow_html=True)
    st.title(title)


def boot_screen():
    ph, shown = st.empty(), []
    lines = ["**LUNAOS INITIALIZATION**", "Lunar Habitat Operating System v1.0", "Habitat: LUNA-1 // Lunar South Pole",
             f"Crew: {m['crew']}", f"Mission duration: {sim.DAYS} days", "", "`SYSTEMS CHECK...`", "✓ Life Support", "✓ Power",
             "✓ Agriculture", "✓ Radiation Protection", "", "**READY FOR COMMAND**"]
    for line in lines:
        shown.append(line)
        ph.markdown("  \n".join(shown))
        time.sleep(.25)
    st.button("ENTER COMMAND DECK", type="primary", on_click=finish_boot)


NAMES = voice.NAMES


def bar_color(v):
    return "#22d3ee" if v > 50 else "#fbbf24" if v > 25 else "#f43f5e"


def line_chart(df, cols, title, ymax=105):
    fig = go.Figure()
    for c, color in cols:
        fig.add_trace(go.Scatter(x=df["day"], y=df[c], name=c.title(), line=dict(color=color, width=2)))
    fig.update_layout(title=title, height=280, margin=dict(l=10, r=10, t=40, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0b1630",
                      yaxis=dict(range=[0, ymax]), legend=dict(orientation="h"))
    return fig


# ================= PAGE 1 =================
if page == "Initialize":
    st.title("LUNAOS // LUNAR OPERATIONS SYSTEM")
    st.write("Keep a crew alive at the Lunar South Pole for 30 days. Batteries, recyclers and shielding all compete for the same power and credits.")
    a, b, c = st.columns(3)
    with a:
        st.subheader("Mission constraints")
        st.write("**Destination:** Lunar South Pole\n\n**Duration:** 30 days\n\n**Type:** Habitat management")
        st.write("**Failure:** oxygen, water, food or battery reaches 0%, structure fails, or the crew is lost.")
    with b:
        st.subheader("Setup")
        busy = m["started"] and not m["over"]
        st.select_slider("Crew size", [2, 3, 4, 5, 6], value=4, key="crew_sel", disabled=busy)
        st.radio("Difficulty", list(sim.DIFFICULTY), index=1, key="diff_sel", horizontal=True, disabled=busy)
    with c:
        st.subheader("Starting supplies")
        n = ss.crew_sel
        st.write(f"Oxygen {n * .84 * sim.STOCK_DAYS['oxygen']:.0f} kg | Water {n * 3.5 * sim.STOCK_DAYS['water']:.0f} L | Food {n * .62 * sim.STOCK_DAYS['food']:.0f} kg")
        st.write(f"Battery {sim.BATTERY_KWH} kWh | Array {sim.ARRAY_KW} kW peak")
        st.write(f"Budget {sim.DIFFICULTY[ss.diff_sel]['cr']} credits plus daily mission funding")
    st.info("Lighting is a simplified game profile (full sun, dusk, long night, dawn), not a model of one specific polar site. See Habitat for what is research-based and what is a game assumption.")
    if m["started"] and not m["over"]:
        st.button("Return to Command Deck", on_click=goto, args=("Command Deck",))
    else:
        st.button("INITIALISE MISSION", type="primary", on_click=start)

# ================= PAGE 2 =================
elif page == "Command Deck":
    p = sim.project(m)
    header("Command Deck")
    if ss.get("boot"):
        boot_screen()
        st.stop()
    st.info(voice.commander_briefing(m, sim))
    st.subheader("A. Mission status")
    c = st.columns(4)
    c[0].metric("Day", f"{m['day']}/{sim.DAYS}", sim.sun_label(m["day"]), delta_color="off")
    c[1].metric("Crew", f"{m['alive']}/{m['crew']}", f"Health {m['hp']:.0f}%", delta_color="off")
    c[2].metric("Credits", f"{m['credits']:.0f}", f"{p['credits']:+.1f}/day (mission funding + science)")
    c[3].metric("Dust on panels", f"{m['dust']:.0f}%", "Reduces solar output", delta_color="off")

    st.subheader("B. Resource monitoring")
    st.caption("Consumables run out. Shielding and structure are conditions that degrade.")
    cols = st.columns(4)
    for col, k in zip(cols, sim.CONS):
        name, unit, hlp = HELP[k]
        v = sim.pct(m, k)
        col.metric(name, f"{m['res'][k]:.0f} {unit}", f"{p['d'][k]:+.1f} {unit}/day")
        col.progress(min(1.0, v / 100), text=f"{v:.0f}%")
        col.caption(hlp)
    with st.expander("How did I do that? Why did my numbers change?"):
        why = st.selectbox("Pick a system", list(NAMES), format_func=NAMES.get, key="why_sel")
        st.markdown(voice.explain(m, why, p))
    cols = st.columns(2)
    cols[0].metric("Shielding", f"{m['shielding']:.0f}%", f"{p['shielding']:+.2f}/day")
    cols[0].caption("Radiation protection condition (simplified).")
    cols[1].metric("Structure", f"{m['structure']:.0f}%", f"{p['structure']:+.2f}/day")
    cols[1].caption("Hull and pressure integrity.")

    st.subheader("C. Habitat overview")
    tiles = [("Habitat core", m["structure"]), ("Life support", min(sim.pct(m, "oxygen"), sim.pct(m, "water"))),
             ("Solar array", 100 - m["dust"]), ("Battery bank", sim.pct(m, "energy")),
             ("Greenhouse", sim.pct(m, "food")), ("Shield berm", m["shielding"])]
    for col, (name, v) in zip(st.columns(len(tiles)), tiles):
        state = "Nominal" if v > 50 else "Degraded" if v > 25 else "Critical"
        col.markdown(f"<div style='border:1px solid #17305a;border-left:4px solid {bar_color(v)};padding:8px;border-radius:4px;background:#091326'>{name}<br><small>{state} ({v:.0f}%)</small></div>", unsafe_allow_html=True)
    for f, on in m["faults"].items():
        if on:
            st.error(f"Active fault: {f.replace('_', ' ')}. It drains stores every day until repaired.")

    st.subheader("D. Daily operations")
    fc = sim.forecast_energy(m)
    low_day, low_val = min(fc, key=lambda x: x[1])
    st.write(f"Power today: **{p['gen']:.0f} kWh** generated, **{p['load']:.0f} kWh** used (net {p['net']:+.0f}).")
    if low_val <= 0:
        dead = next(d for d, v in fc if v <= 0)
        st.error(f"Forecast: the battery runs out on day {dead} at current settings. Shed loads in Habitat.")
    else:
        st.success(f"Forecast: battery bottoms out at {low_val:.0f}% on day {low_day} at current settings.")
    ff = pd.DataFrame(fc, columns=["day", "battery"])
    ff["sunlight"] = [sim.sun_fraction(d) * 100 for d in ff["day"]]
    st.plotly_chart(line_chart(ff, [("battery", "#22d3ee"), ("sunlight", "#8b5cf6")], "Projected battery % and sunlight % (events not included)"), width="stretch")
    if m["event"]:
        st.warning(f"Active event: {EVENTS[m['event']]['title']}. Respond in Mission Feed before advancing.")
    st.button("Complete final day" if m["day"] >= sim.DAYS else "Advance to next day", type="primary", on_click=advance)

# ================= PAGE 3 =================
elif page == "Habitat":
    header("Habitat")
    st.caption("Adjust the sliders to preview the daily effect, then press Apply to commit.")
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Life support")
        st.slider("Oxygen recycling setpoint (%)", 40, 100, key="w_o2_recycle",
                  help=f"Actual recovery is capped at {(.85 + .03 * m['upgrades']['life']) * 100:.0f}% by hardware.")
        st.slider("Water recycling setpoint (%)", 40, 100, key="w_water_recycle",
                  help=f"Capped at {(.90 + .02 * m['upgrades']['life']) * 100:.0f}% by hardware.")
        st.subheader("Power")
        st.slider("Science and operations load (%)", 0, 100, key="w_science", help="Non-essential power. It earns credits but drains the battery.")
        st.subheader("Agriculture")
        st.slider("Hydroponics output (%)", 0, 100, key="w_farm", help="More food, but also more water and power.")
        st.subheader("Protection")
        st.slider("Maintenance effort (%)", 0, 100, key="w_maint", help="Restores shielding and structure. Costs credits each day.")
    new = {k: ss["w_" + k] for k in sim.DEFAULTS}
    cur, pre = sim.project(m), sim.project(m, new)
    with right:
        st.subheader("Predicted effect per day")
        rows = [("Oxygen kg", "oxygen"), ("Water L", "water"), ("Food kg", "food"), ("Battery kWh", "energy")]
        df = pd.DataFrame({"Now": [cur["d"][k] for _, k in rows] + [cur["load"], cur["credits"]],
                           "After apply": [pre["d"][k] for _, k in rows] + [pre["load"], pre["credits"]]},
                          index=[r[0] for r in rows] + ["Power load kWh", "Credits"]).round(2)
        st.dataframe(df, width="stretch")
        st.caption("Power load now: " + ", ".join(f"{k} {v:.0f}" for k, v in pre["loads"].items()))
        fc = sim.forecast_energy(m, new)
        dead = next((d for d, v in fc if v <= 0), None)
        if dead:
            st.error(f"With these settings the battery runs out on day {dead}.")
        else:
            st.success(f"Battery minimum with these settings: {min(v for _, v in fc):.0f}%.")
        st.button("Apply settings", type="primary", on_click=apply_settings)

    st.subheader("Upgrades and repairs")
    descs = {"life": "Higher recycling ceiling", "power": "More solar output and battery capacity",
             "agri": "More food per % output", "protect": "Slower shield decay, better maintenance"}
    for col, key in zip(st.columns(4), sim.UP_NAMES):
        lvl = m["upgrades"][key]
        col.markdown(f"**{sim.UP_NAMES[key]}** L{lvl}/5")
        col.caption(descs[key])
        col.button("Max" if lvl >= 5 else f"Upgrade ({sim.upgrade_cost(m, key)} cr)", key="up" + key,
                   disabled=lvl >= 5 or m["credits"] < sim.upgrade_cost(m, key), on_click=act, args=(sim.upgrade, key))
    r = st.columns(4)
    r[0].button("Clean panels (20 cr)", on_click=act, args=(sim.clean_panels,), disabled=m["credits"] < 20)
    r[1].button("Emergency repair (40 cr)", on_click=act, args=(sim.emergency_repair,), disabled=m["credits"] < 40)
    for i, f in enumerate(m["faults"]):
        if m["faults"][f]:
            r[2 + i].button(f"Repair {f.replace('_', ' ')} (30 cr)", on_click=act, args=(sim.repair_fault, f), disabled=m["credits"] < 30)

    st.subheader("Science behind the simulation")
    for name, d in SCIENCE.items():
        with st.expander(name):
            st.markdown("**Research-based**\n" + "\n".join(f"- {x}" for x in d["research"]))
            st.markdown("**Game assumptions**\n" + "\n".join(f"- {x}" for x in d["assumptions"]))

# ================= PAGE 4 =================
elif page == "Mission Feed":
    header("Mission Feed")
    if m["event"]:
        ev = EVENTS[m["event"]]
        st.error(f"**{ev['title']}**  \n{ev['desc']}")
        for i, ch in enumerate(ev["choices"]):
            a, b = st.columns([4, 1])
            a.markdown(f"**{ch['label']}**  \n<small>{describe(ch)}</small>", unsafe_allow_html=True)
            b.button("Choose", key=f"ch{i}", disabled=ch["cost"] > m["credits"], on_click=act, args=(sim.resolve_event, i))
    else:
        st.info("No active event. Advance the day to see what happens.")
    st.subheader("Mission log")
    for e in m["log"]:
        st.markdown(f"**Day {e['day']}** `{e['type']}` {e['msg']}")

# ================= PAGE 5 =================
else:
    A = sim.analyse(m)
    st.title("MISSION DEBRIEF")
    st.markdown(f"### {sim.DAYS if m['won'] else m['day']} DAYS. {m['crew']} CREW. 1 HABITAT.")
    st.subheader("MISSION SUCCESS" if m["won"] else "MISSION FAILED")
    st.write(m["reason"])
    if A:
        style, desc = voice.command_style(m)
        st.subheader("Your command style")
        st.markdown(f"**{style}**  \n{desc}")
        top = A["top_decisions"][0] if A["top_decisions"] else None
        st.subheader("Your toughest decision")
        st.markdown(f"**Day {top['day']}: {top['event']}**  \nYou chose: {top['choice']}" if top else "No incident required a decision this mission.")
        st.subheader("What the simulation taught you")
        st.markdown(voice.taught(A, m))
        H = pd.DataFrame(m["history"])
        c = st.columns(4)
        c[0].metric("Days survived", m["day"] if not m["won"] else sim.DAYS)
        c[1].metric("Crew survival", f"{m['alive']}/{m['crew']}")
        c[2].metric("Energy generated / used", f"{A['gen']:.0f} / {A['load']:.0f} kWh")
        c[3].metric("Score", A["score"])
        st.plotly_chart(line_chart(H, [("oxygen", "#22d3ee"), ("water", "#8b5cf6"), ("food", "#34d399"), ("energy", "#fbbf24")], "Consumables (% of capacity)"), width="stretch")
        st.plotly_chart(line_chart(H.rename(columns={"gen": "generated", "load": "consumed"}), [("generated", "#fbbf24"), ("consumed", "#f43f5e")], "Daily power (kWh)", ymax=max(H["gen"].max(), H["load"].max()) * 1.1), width="stretch")

        st.header("What your decisions did")
        k, (v, d) = A["worst_res"], A["lowest"][A["worst_res"]]
        st.write(f"**Lowest point:** {HELP[k][0]} fell to {v:.0f}% on day {d}.")
        night = A["night_prep"]
        if night is not None:
            verdict = "good preparation" if night >= 90 else "the battery was only partly charged" if night >= 60 else "the battery was poorly prepared"
            st.write(f"**Night preparation:** the battery was at {night:.0f}% at the end of day 15 ({verdict}).")
        st.write(f"**Generation vs use:** {A['gen']:.0f} kWh generated and {A['load']:.0f} kWh consumed ({A['gen'] / max(A['load'], 1) * 100:.0f}% coverage).")
        st.write(f"**Most trouble:** {A['worst_sys']} ({m['issues'][A['worst_sys']]} incidents and warnings).")
        if A["top_decisions"]:
            st.write("**Biggest-impact decisions:**")
            for t in A["top_decisions"]:
                st.write(f"- Day {t['day']}, {t['event']}: {t['choice']}")
        st.subheader("The science behind it")
        st.write(SCIENCE[A["worst_sys"]]["lesson"])
    st.button("New mission", type="primary", on_click=new_mission)
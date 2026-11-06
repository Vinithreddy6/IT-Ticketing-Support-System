"""IT Helpdesk - role-based ticketing workspace (Streamlit + MySQL)."""
import html
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from mysql.connector import Error, IntegrityError

from database import (
    PRIORITIES, SLA_HOURS, STATUSES,
    initialize_database, seed_demo_data, get_user_by_email, verify_password,
    create_user, get_categories, create_ticket, fetch_tickets, get_ticket,
    get_staff, update_ticket, claim_ticket, add_comment, get_timeline,
    get_dashboard_stats, get_admin_overview, get_advanced_analytics,
    get_all_users, set_user_role,
)

st.set_page_config(page_title="IT Helpdesk", page_icon="🎫", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
PRIORITY_COLORS = {"Critical": "#dc2626", "High": "#f97316", "Medium": "#eab308", "Low": "#22c55e"}
PRIORITY_DOT = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
STATUS_COLORS = {"Open": "#3b82f6", "In Progress": "#8b5cf6", "Resolved": "#10b981", "Closed": "#94a3b8"}
ROLE_ICON = {"Employee": "👤", "IT Staff": "🛠️", "Admin": "🛡️"}
STAFF_ROLES = ("IT Staff", "Admin")
TONES = {
    "indigo": ("#eef2ff", "#4f46e5"), "blue": ("#eff6ff", "#2563eb"),
    "amber": ("#fffbeb", "#d97706"), "red": ("#fef2f2", "#dc2626"),
    "green": ("#ecfdf5", "#059669"), "violet": ("#f5f3ff", "#7c3aed"),
    "slate": ("#f1f5f9", "#475569"),
}
AVATAR_COLORS = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]
PAGES = {}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp { font-family:'DM Sans',system-ui,sans-serif; }
.stApp { background:radial-gradient(1200px 500px at 85% -10%,#e8ebff 0%,rgba(232,235,255,0) 60%),#f5f6fb; }
#MainMenu, footer { visibility:hidden; }
header[data-testid="stHeader"] { background:transparent; }
.block-container { padding-top:1.6rem; padding-bottom:3rem; max-width:1380px; animation:fadeUp .4s ease both; }
@keyframes fadeUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }
h1,h2,h3,h4 { letter-spacing:-.015em; color:#0f172a; }

/* sidebar */
[data-testid="stSidebar"] { background:#ffffff; border-right:1px solid #e8eaf3; }
[data-testid="stSidebar"] a { border-radius:10px; transition:background .15s ease, transform .15s ease; }
[data-testid="stSidebar"] a:hover { transform:translateX(2px); }
.profile { display:flex; gap:.75rem; align-items:center; padding:.8rem; border:1px solid #eceef6; border-radius:14px; background:#fafbff; margin:.4rem 0 .6rem; }
.pname { font-weight:700; color:#0f172a; line-height:1.2; }
.prole { font-size:.8rem; color:#64748b; }
.avatar { display:inline-flex; align-items:center; justify-content:center; border-radius:50%; color:#fff; font-weight:700; flex:none; }

/* hero */
.hero { padding:1.7rem 2rem; border-radius:22px; color:#fff; margin-bottom:1.2rem; position:relative; overflow:hidden;
        background:linear-gradient(120deg,#1e1b4b 0%,#4338ca 55%,#6366f1 100%); box-shadow:0 18px 40px rgba(67,56,202,.22); }
.hero:after { content:""; position:absolute; right:-60px; top:-80px; width:280px; height:280px; border-radius:50%; background:rgba(255,255,255,.08); }
.hero .eyebrow { font-size:.72rem; letter-spacing:.16em; font-weight:700; color:#c7d2fe; text-transform:uppercase; margin-bottom:.5rem; }
.hero h1 { color:#fff!important; font-size:2rem; font-weight:800; margin:0 0 .3rem; }
.hero p { color:#dbe4ff; margin:0; font-size:1rem; }
.pagehead h1 { font-size:1.75rem; font-weight:800; margin:0; }
.pagehead p { color:#64748b; margin:.2rem 0 1rem; }

/* kpi */
.kpi { display:flex; gap:.9rem; align-items:center; background:#fff; border:1px solid #eceef6; border-radius:18px; padding:1rem 1.1rem;
       box-shadow:0 4px 16px rgba(30,41,59,.04); transition:transform .18s ease, box-shadow .18s ease; height:100%; }
.kpi:hover { transform:translateY(-3px); box-shadow:0 12px 28px rgba(30,41,59,.09); }
.kpi-ico { width:46px; height:46px; border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:1.35rem; flex:none; }
.kpi-label { color:#64748b; font-size:.8rem; font-weight:600; }
.kpi-value { color:#0f172a; font-size:1.65rem; font-weight:800; line-height:1.15; }
.kpi-sub { color:#94a3b8; font-size:.74rem; }

/* chips */
.chip { display:inline-flex; align-items:center; gap:.25rem; padding:.18rem .6rem; border-radius:999px; font-size:.74rem; font-weight:700;
        color:var(--c); background:color-mix(in srgb,var(--c) 12%,white); white-space:nowrap; }
.muted { color:#94a3b8; font-size:.82rem; }

/* ticket card */
.tcard { display:flex; gap:.9rem; align-items:stretch; background:#fff; border:1px solid #eceef6; border-left:5px solid var(--p);
         border-radius:16px; padding:.95rem 1.1rem; box-shadow:0 3px 12px rgba(30,41,59,.035); transition:transform .15s ease, box-shadow .15s ease; }
.tcard:hover { transform:translateY(-2px); box-shadow:0 10px 24px rgba(30,41,59,.08); }
.tcard .rank { width:30px; height:30px; border-radius:10px; background:#eef2ff; color:#4f46e5; font-weight:800; display:flex; align-items:center; justify-content:center; flex:none; }
.tcard .ttl { font-weight:700; color:#0f172a; font-size:1.02rem; margin:.1rem 0 .45rem; }
.tcard .tid { color:#94a3b8; font-weight:600; font-size:.82rem; margin-right:.35rem; }
.tcard .chips { display:flex; flex-wrap:wrap; gap:.35rem; margin-bottom:.45rem; }
.tcard .who { display:flex; align-items:center; gap:.45rem; color:#475569; font-size:.84rem; flex-wrap:wrap; }

/* next-up */
.nextup { border-radius:18px; padding:1.1rem 1.4rem; color:#fff; margin-bottom:1rem; background:linear-gradient(120deg,#7c2d12,#ea580c 70%,#fb923c); box-shadow:0 12px 28px rgba(234,88,12,.22); }
.nextup small { letter-spacing:.14em; font-weight:700; text-transform:uppercase; opacity:.85; }
.nextup b { display:block; font-size:1.25rem; margin:.2rem 0; }

/* stepper */
.stepper { display:flex; margin:.4rem 0 1.1rem; }
.step { flex:1; text-align:center; position:relative; }
.step .bub { width:30px; height:30px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; background:#e2e8f0; color:#64748b; font-weight:700; font-size:.82rem; position:relative; z-index:1; }
.step .lbl { display:block; font-size:.76rem; color:#94a3b8; margin-top:.3rem; font-weight:600; }
.step:not(:last-child)::after { content:""; position:absolute; top:14px; left:calc(50% + 17px); right:calc(-50% + 17px); height:3px; background:#e2e8f0; }
.step.done .bub { background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff; }
.step.done:not(:last-child)::after { background:linear-gradient(90deg,#6366f1,#8b5cf6); }
.step.done .lbl, .step.active .lbl { color:#334155; }
.step.active .bub { background:#fff; color:#6366f1; box-shadow:0 0 0 3px #c7d2fe; border:2px solid #6366f1; }

/* info grid, timeline */
.infogrid { display:grid; grid-template-columns:repeat(3,1fr); gap:.7rem; margin:.4rem 0 1rem; }
.infogrid div { background:#f8fafc; border:1px solid #eef0f6; border-radius:12px; padding:.6rem .8rem; }
.infogrid small { color:#94a3b8; font-weight:600; display:block; font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; }
.descbox { background:#f8fafc; border:1px solid #eef0f6; border-radius:12px; padding:.9rem 1rem; color:#334155; white-space:pre-wrap; }
.event { color:#64748b; font-size:.84rem; padding:.28rem 0 .28rem .2rem; }
.event .dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#a5b4fc; margin-right:.55rem; }
.feed .event { border-bottom:1px solid #f1f3f9; padding:.55rem 0; }

/* roles + login */
.role-grid { display:grid; gap:.7rem; margin-top:1.2rem; }
.role-card { display:flex; gap:.85rem; align-items:flex-start; background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.16); border-radius:16px; padding:.85rem 1rem; backdrop-filter:blur(6px); }
.role-card .ri { font-size:1.5rem; }
.role-card b { display:block; color:#fff; } .role-card span { color:#dbe4ff; font-size:.88rem; }
.brand { display:flex; align-items:center; gap:.7rem; font-weight:800; font-size:1.15rem; margin-bottom:1.1rem; }
.brand i { font-style:normal; width:40px; height:40px; border-radius:12px; background:rgba(255,255,255,.16); display:flex; align-items:center; justify-content:center; font-size:1.3rem; }
.lightcard { background:#fff; border:1px solid #eceef6; border-radius:18px; padding:1.1rem 1.3rem; box-shadow:0 4px 16px rgba(30,41,59,.04); }
.lightcard h4 { margin:.1rem 0 .5rem; }
.empty { text-align:center; padding:2.2rem 1rem; background:#fff; border:1.5px dashed #d9dcec; border-radius:18px; color:#64748b; }
.empty .ei { font-size:2.2rem; }
.team { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:.9rem; }
.tm { background:#fff; border:1px solid #eceef6; border-radius:18px; padding:1rem 1.1rem; box-shadow:0 4px 16px rgba(30,41,59,.04); transition:transform .18s ease, box-shadow .18s ease; }
.tm:hover { transform:translateY(-3px); box-shadow:0 12px 28px rgba(30,41,59,.09); }
.tm .top { display:flex; gap:.7rem; align-items:center; margin-bottom:.8rem; }
.tm .nums { display:grid; grid-template-columns:repeat(3,1fr); text-align:center; margin:.7rem 0 .2rem; }
.tm .nums b { font-size:1.2rem; display:block; color:#0f172a; } .tm .nums small { color:#94a3b8; font-size:.72rem; }
.bar { height:8px; border-radius:99px; background:#eef0f7; overflow:hidden; }
.bar > i { display:block; height:100%; border-radius:99px; background:linear-gradient(90deg,#6366f1,#22c55e); }
table.sla { width:100%; border-collapse:collapse; } table.sla td, table.sla th { padding:.5rem .6rem; border-bottom:1px solid #f1f3f9; text-align:left; font-size:.92rem; }

/* streamlit widgets */
.stButton>button, .stFormSubmitButton>button { border-radius:12px; font-weight:700; transition:transform .12s ease, box-shadow .12s ease; }
.stButton>button:hover, .stFormSubmitButton>button:hover { transform:translateY(-1px); box-shadow:0 6px 16px rgba(79,70,229,.18); }
button[kind="primary"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] { background:linear-gradient(135deg,#4f46e5,#7c3aed)!important; border:none!important; }
.stTextInput input, .stTextArea textarea, div[data-baseweb="select"]>div { border-radius:11px!important; }
[data-testid="stDataFrame"] { border:1px solid #eceef6; border-radius:14px; overflow:hidden; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div > .stForm), [data-testid="stForm"] { border-radius:16px; }
[data-testid="stTabs"] button { font-weight:700; }
@media (max-width:900px){ .infogrid{grid-template-columns:1fr 1fr;} .hero h1{font-size:1.5rem;} }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Small UI helpers
# ---------------------------------------------------------------------------
def esc(value):
    return html.escape("" if value is None else str(value))


def fmt_dt(dt):
    return dt.strftime("%d %b, %H:%M") if dt else "—"


def human_minutes(m):
    m = abs(int(m))
    if m < 60:
        return f"{m}m"
    if m < 1440:
        return f"{m // 60}h"
    return f"{m // 1440}d {(m % 1440) // 60}h" if m < 4 * 1440 else f"{m // 1440}d"


def avatar(name, size=30):
    name = name or "?"
    parts = name.split()
    initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()
    color = AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)]
    return (f'<span class="avatar" style="width:{size}px;height:{size}px;background:{color};'
            f'font-size:{size * 0.4:.0f}px">{esc(initials)}</span>')


def chip(text, color, prefix=""):
    return f'<span class="chip" style="--c:{color}">{prefix}{esc(text)}</span>'


def priority_chip(p):
    return chip(p, PRIORITY_COLORS[p], "● ")


def status_chip(s):
    return chip(s, STATUS_COLORS[s])


def due_chip(t):
    if t["status"] in ("Resolved", "Closed"):
        return chip("Completed", "#059669", "✓ ")
    if t.get("due_date") is None or t.get("minutes_left") is None:
        return ""
    m = int(t["minutes_left"])
    if m < 0:
        return chip(f"Overdue by {human_minutes(m)}", "#dc2626", "⚠ ")
    if m < 24 * 60:
        return chip(f"Due in {human_minutes(m)}", "#d97706", "⏰ ")
    return chip(f"Due in {human_minutes(m)}", "#475569", "🗓 ")


def kpi_row(items):
    cols = st.columns(len(items))
    for col, (icon, label, value, sub, tone) in zip(cols, items):
        bg, fg = TONES[tone]
        col.markdown(
            f'<div class="kpi"><div class="kpi-ico" style="background:{bg};color:{fg}">{icon}</div>'
            f'<div><div class="kpi-label">{esc(label)}</div><div class="kpi-value">{value}</div>'
            f'<div class="kpi-sub">{esc(sub)}</div></div></div>', unsafe_allow_html=True)


def hero(eyebrow, title, subtitle):
    st.markdown(f'<div class="hero"><div class="eyebrow">{esc(eyebrow)}</div><h1>{title}</h1>'
                f'<p>{esc(subtitle)}</p></div>', unsafe_allow_html=True)


def page_header(title, subtitle=""):
    st.markdown(f'<div class="pagehead"><h1>{title}</h1><p>{esc(subtitle)}</p></div>', unsafe_allow_html=True)


def empty_state(icon, title, text=""):
    st.markdown(f'<div class="empty"><div class="ei">{icon}</div><b>{esc(title)}</b><br>{esc(text)}</div>',
                unsafe_allow_html=True)


def flash(message, icon="✅"):
    st.session_state["_flash"] = (message, icon)


def greeting():
    h = datetime.now().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"


def lifecycle_html(t):
    stage = {"Open": 1 if t["assigned_to"] else 0, "In Progress": 2, "Resolved": 3, "Closed": 4}[t["status"]]
    labels = ["Raised", "Assigned", "In progress", "Resolved", "Closed"]
    out = []
    for i, label in enumerate(labels):
        css = "done" if i < stage or stage == 4 else "active" if i == stage else ""
        out.append(f'<div class="step {css}"><span class="bub">{"✓" if css == "done" else i + 1}</span>'
                   f'<span class="lbl">{label}</span></div>')
    return f'<div class="stepper">{"".join(out)}</div>'


# ---------------------------------------------------------------------------
# Ticket cards + detail dialog
# ---------------------------------------------------------------------------
def ticket_card_html(t, user, rank=None):
    if t["assignee_name"]:
        owner = f'{avatar(t["assignee_name"], 22)} <span>{esc(t["assignee_name"])}</span>'
    elif user["role"] == "Employee":
        owner = '<span class="muted">⏳ Waiting for IT to pick this up</span>'
    else:
        owner = '<span class="chip" style="--c:#dc2626">Unassigned</span>'
    who = f'Raised by {esc(t["requester_name"])} · ' if user["role"] != "Employee" else ""
    badge = f'<div class="rank">{rank}</div>' if rank else ""
    return (
        f'<div class="tcard" style="--p:{PRIORITY_COLORS[t["priority"]]}">{badge}<div style="flex:1;min-width:0">'
        f'<div class="ttl"><span class="tid">#{t["ticket_id"]}</span>{esc(t["title"])}</div>'
        f'<div class="chips">{priority_chip(t["priority"])}{status_chip(t["status"])}'
        f'{chip(t["category_name"], "#64748b")}{due_chip(t)}</div>'
        f'<div class="who">{who}{owner}<span class="muted">· {fmt_dt(t["created_at"])}</span></div>'
        f'</div></div>')


def ticket_cards(user, rows, key, page_size=10, rank=False, allow_claim=True):
    if not rows:
        empty_state("🎉", "Nothing here", "No tickets match this view.")
        return
    shown_key = f"_shown_{key}"
    shown = st.session_state.get(shown_key, page_size)
    for i, t in enumerate(rows[:shown], 1):
        left, right = st.columns([6.4, 1.1], vertical_alignment="center", gap="small")
        left.markdown(ticket_card_html(t, user, i if rank else None), unsafe_allow_html=True)
        with right:
            if st.button("Open", key=f"{key}_open_{t['ticket_id']}", icon=":material/open_in_new:",
                         width="stretch"):
                ticket_dialog(t["ticket_id"])
            if (allow_claim and user["role"] == "IT Staff" and t["assigned_to"] is None
                    and t["status"] in ("Open", "In Progress")):
                if st.button("Pick up", key=f"{key}_claim_{t['ticket_id']}", icon=":material/bolt:",
                             type="primary", width="stretch"):
                    if claim_ticket(t["ticket_id"], user["user_id"]):
                        flash(f"Ticket #{t['ticket_id']} is now yours.", "⚡")
                    else:
                        flash("Someone else picked this ticket up first.", "ℹ️")
                    st.rerun()
    if len(rows) > shown:
        if st.button(f"Show {min(page_size, len(rows) - shown)} more  ·  {len(rows) - shown} remaining",
                     key=f"{key}_more"):
            st.session_state[shown_key] = shown + page_size
            st.rerun()


@st.dialog("Ticket details", width="large")
def ticket_dialog(ticket_id):
    user = st.session_state.user
    t = get_ticket(ticket_id)
    if not t:
        st.error("Ticket not found.")
        return
    if user["role"] == "Employee" and t["user_id"] != user["user_id"]:
        st.error("You do not have permission to view this ticket.")
        return

    st.markdown(
        f'<div class="chips" style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.3rem">'
        f'{priority_chip(t["priority"])}{status_chip(t["status"])}{chip(t["category_name"], "#64748b")}{due_chip(t)}</div>'
        f'<h3 style="margin:.2rem 0 .6rem">#{t["ticket_id"]} · {esc(t["title"])}</h3>', unsafe_allow_html=True)
    st.markdown(lifecycle_html(t), unsafe_allow_html=True)

    assignee = (f'{avatar(t["assignee_name"], 22)} {esc(t["assignee_name"])}' if t["assignee_name"]
                else '<span class="muted">Not assigned yet</span>')
    st.markdown(
        '<div class="infogrid">'
        f'<div><small>Raised by</small>{avatar(t["requester_name"], 22)} {esc(t["requester_name"])}</div>'
        f'<div><small>Assigned to</small>{assignee}</div>'
        f'<div><small>Deadline</small>{fmt_dt(t["due_date"])}</div>'
        f'<div><small>Created</small>{fmt_dt(t["created_at"])}</div>'
        f'<div><small>Last update</small>{fmt_dt(t["updated_at"])}</div>'
        f'<div><small>Resolved</small>{fmt_dt(t["resolved_at"])}</div></div>'
        f'<div class="descbox">{esc(t["description"])}</div>', unsafe_allow_html=True)

    if user["role"] in STAFF_ROLES:
        st.write("")
        with st.container(border=True):
            st.markdown("##### 🛠️ Manage this ticket")
            if (user["role"] == "IT Staff" and t["assigned_to"] is None
                    and t["status"] in ("Open", "In Progress")):
                if st.button("Pick up this ticket", icon=":material/bolt:", type="primary",
                             key=f"dlg_claim_{ticket_id}"):
                    if claim_ticket(ticket_id, user["user_id"]):
                        flash(f"Ticket #{ticket_id} is now yours.", "⚡")
                    st.rerun()
            staff = get_staff()
            options = {"— Unassigned —": None}
            options.update({f"{s['name']} · {s['role']} · {int(s['active_tickets'])} active": s["user_id"]
                            for s in staff})
            labels = list(options)
            current = next((k for k, v in options.items() if v == t["assigned_to"]), labels[0])
            due = t["due_date"] or (datetime.now() + timedelta(hours=SLA_HOURS[t["priority"]]))
            with st.form(f"manage_{ticket_id}", border=False):
                c1, c2 = st.columns(2)
                status = c1.selectbox("Status", STATUSES, index=STATUSES.index(t["status"]))
                priority = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(t["priority"]),
                                        format_func=lambda p: f"{PRIORITY_DOT[p]} {p}")
                chosen = st.selectbox("Assign to", labels, index=labels.index(current),
                                      help="The number shows how many open tickets each person already has.")
                d1, d2 = st.columns(2)
                new_date = d1.date_input("Deadline date", value=due.date())
                new_time = d2.time_input("Deadline time", value=due.time().replace(second=0, microsecond=0),
                                         step=900)
                recalc = st.checkbox("Reset the deadline to the standard target for this priority")
                save = st.form_submit_button("Save changes", type="primary", icon=":material/save:",
                                             width="stretch")
            if save:
                if status != "Open" and options[chosen] is None:
                    st.error("Assign this ticket to someone before moving it past Open.")
                else:
                    update_ticket(ticket_id, user["user_id"], status, priority, options[chosen],
                                  datetime.combine(new_date, new_time), recalc)
                    flash(f"Ticket #{ticket_id} updated.")
                    st.rerun()
    elif not t["assigned_to"] and t["status"] == "Open":
        st.info("Your ticket is in the queue. IT will assign someone shortly.", icon="⏳")

    st.markdown("##### 💬 Activity & conversation")
    timeline = get_timeline(ticket_id)
    with st.container(height=300, border=False):
        for item in timeline:
            when = fmt_dt(item["created_at"])
            if item["kind"] == "event":
                st.markdown(f'<div class="event"><span class="dot"></span><b>{esc(item["actor"])}</b> '
                            f'{esc(item["text"])} <span class="muted">· {when}</span></div>',
                            unsafe_allow_html=True)
            else:
                with st.chat_message("assistant" if item["actor_role"] in STAFF_ROLES else "user"):
                    st.markdown(f'<b>{esc(item["actor"])}</b> <span class="muted">· {esc(item["actor_role"])} · {when}</span>',
                                unsafe_allow_html=True)
                    st.write(item["text"])
    with st.form(f"comment_{ticket_id}", clear_on_submit=True, border=False):
        message = st.text_area("Add a comment or update", height=80,
                               placeholder="Share an update, a question, or what you tried...")
        send = st.form_submit_button("Post comment", icon=":material/send:")
    if send:
        if len(message.strip()) < 2:
            st.error("Comment is too short.")
        else:
            add_comment(ticket_id, user["user_id"], message)
            st.rerun()


# ---------------------------------------------------------------------------
# Login / welcome
# ---------------------------------------------------------------------------
def do_login(email, password):
    user = get_user_by_email(email or "")
    if user and verify_password(password or "", user["password_hash"]):
        st.session_state.user = {k: user[k] for k in ("user_id", "name", "email", "role")}
        return True
    return False


def login_screen():
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
                "[data-testid='collapsedControl']{display:none}</style>", unsafe_allow_html=True)
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.markdown("""
<div class="hero" style="padding:2.2rem 2.2rem 2.4rem;min-height:600px">
  <div class="brand"><i>🎫</i>IT Helpdesk</div>
  <div class="eyebrow">Service desk workspace</div>
  <h1 style="font-size:2.4rem;line-height:1.15">Get tech problems solved,<br>fast and on time.</h1>
  <p style="max-width:520px">Report an issue, see who is fixing it, and know exactly when it will be done.
     Everyone works from the same live ticket.</p>
  <div class="role-grid">
    <div class="role-card"><div class="ri">👤</div><div><b>Employee</b><span>Having an IT problem? Raise a ticket with a priority and description, then follow it until it is fixed.</span></div></div>
    <div class="role-card"><div class="ri">🛠️</div><div><b>IT Staff</b><span>The technicians. Pick up or receive tickets, work through them by priority and deadline, and mark them resolved.</span></div></div>
    <div class="role-card"><div class="ri">🛡️</div><div><b>Admin</b><span>The IT manager. Assigns work, tracks every ticket and sees how the whole team is performing.</span></div></div>
  </div>
</div>""", unsafe_allow_html=True)
    with right:
        st.write("")
        st.markdown("<h2 style='margin-bottom:0'>Welcome 👋</h2><p class='muted' style='font-size:.95rem'>Sign in to your workspace or create an employee account.</p>",
                    unsafe_allow_html=True)
        with st.container(border=True):
            tab_in, tab_new = st.tabs(["🔐 Sign in", "✨ Create account"])
            with tab_in:
                with st.form("login_form", border=False):
                    email = st.text_input("Work email", placeholder="you@company.com")
                    password = st.text_input("Password", type="password", placeholder="Your password")
                    submitted = st.form_submit_button("Sign in", type="primary", icon=":material/login:",
                                                      width="stretch")
                if submitted:
                    if do_login(email, password):
                        st.rerun()
                    st.error("Invalid email or password.")
            with tab_new:
                with st.form("register_form", border=False):
                    name = st.text_input("Full name")
                    new_email = st.text_input("Work email", key="reg_email")
                    p1 = st.text_input("Password", type="password", key="reg_p1", help="At least 8 characters")
                    p2 = st.text_input("Confirm password", type="password", key="reg_p2")
                    register = st.form_submit_button("Create account", icon=":material/person_add:",
                                                     width="stretch")
                if register:
                    if not name.strip() or "@" not in new_email or len(p1) < 8:
                        st.error("Enter your name, a valid email and a password of at least 8 characters.")
                    elif p1 != p2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            create_user(name, new_email, p1)
                            st.success("Account created. Switch to **Sign in** to continue.")
                        except IntegrityError:
                            st.error("That email is already registered.")
        st.markdown("<p class='muted' style='text-align:center;margin:.9rem 0 .3rem'>— or explore with a demo account —</p>",
                    unsafe_allow_html=True)
        demos = [("Employee", "employee@demo.com", "Employee@123", ":material/person:"),
                 ("IT Staff", "itstaff@demo.com", "ITStaff@123", ":material/build:"),
                 ("Admin", "admin@demo.com", "Admin@123", ":material/shield_person:")]
        for col, (label, mail, pw, icon) in zip(st.columns(3), demos):
            if col.button(label, icon=icon, key=f"demo_{label}", width="stretch"):
                if do_login(mail, pw):
                    st.rerun()
                st.error("Demo account not found.")
        st.caption("Demo accounts are for local testing only - remove them before real use.")


# ---------------------------------------------------------------------------
# Employee pages
# ---------------------------------------------------------------------------
def employee_home():
    user = st.session_state.user
    stats = get_dashboard_stats(user)
    hero("Employee workspace", f"{greeting()}, {esc(user['name'].split()[0])} 👋",
         "Raise an issue, then follow it from first report to fix.")
    kpi_row([
        ("🎫", "Tickets raised", stats["total"], "all time", "indigo"),
        ("⏳", "Waiting", stats["open_count"], "not started yet", "blue"),
        ("🔧", "Being fixed", stats["progress_count"], "IT is working on it", "violet"),
        ("✅", "Resolved", stats["resolved_count"] + stats["closed_count"], "done", "green"),
    ])
    st.write("")
    left, right = st.columns([2.2, 1], gap="large")
    with left:
        st.markdown("#### Your recent tickets")
        ticket_cards(user, fetch_tickets(user, order="newest", limit=5), "emp_home", page_size=5)
    with right:
        st.markdown("#### Need help?")
        st.markdown('<div class="lightcard">Something broken or missing? Tell IT in a minute. '
                    'The more detail you give, the faster it gets fixed.</div>', unsafe_allow_html=True)
        st.write("")
        if st.button("Raise a new ticket", icon=":material/add_circle:", type="primary", width="stretch"):
            st.switch_page(PAGES["new"])
        if st.button("See how it works", icon=":material/help:", width="stretch"):
            st.switch_page(PAGES["help"])


PRIORITY_HELP = {
    "Low": "Not urgent - a request or minor annoyance.",
    "Medium": "Slows you down, but you can still work.",
    "High": "Seriously affects your work.",
    "Critical": "You or your team cannot work at all.",
}


def new_ticket_page():
    user = st.session_state.user
    page_header("Raise a ticket", "Describe the problem. IT will pick it up and keep you updated.")
    categories = get_categories()
    category_map = {c["category_name"]: c["category_id"] for c in categories}
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        with st.container(border=True):
            with st.form("create_ticket_form", clear_on_submit=True, border=False):
                title = st.text_input("What is the problem?", max_chars=180,
                                      placeholder="e.g. Cannot connect to the office Wi-Fi")
                c1, c2 = st.columns(2)
                category = c1.selectbox("Category", list(category_map))
                priority = c2.selectbox("Priority", PRIORITIES, index=1,
                                        format_func=lambda p: f"{PRIORITY_DOT[p]} {p}")
                description = st.text_area("Details", height=170,
                                           placeholder="What happened? Any error message? When did it start? What have you already tried?")
                submit = st.form_submit_button("Submit ticket", type="primary", icon=":material/send:",
                                               width="stretch")
        if submit:
            if len(title.strip()) < 5 or len(description.strip()) < 10:
                st.error("Please add a title (5+ characters) and details (10+ characters).")
            else:
                ticket_id = create_ticket(user["user_id"], category_map[category], title, description, priority)
                st.balloons()
                st.success(f"Ticket **#{ticket_id}** submitted. Target resolution: "
                           f"**{human_minutes(SLA_HOURS[priority] * 60)}** ({priority} priority).")
                if st.button("Go to my tickets", icon=":material/confirmation_number:"):
                    st.switch_page(PAGES["mine"])
    with right:
        rows = "".join(f"<tr><td>{priority_chip(p)}</td><td>{esc(PRIORITY_HELP[p])}</td>"
                       f"<td><b>{human_minutes(SLA_HOURS[p] * 60)}</b></td></tr>" for p in reversed(PRIORITIES))
        st.markdown(f'<div class="lightcard"><h4>Which priority?</h4><table class="sla">'
                    f'<tr><th>Level</th><th>Use when</th><th>Target</th></tr>{rows}</table></div>',
                    unsafe_allow_html=True)
        st.write("")
        st.markdown('<div class="lightcard"><h4>💡 Tips for a faster fix</h4>'
                    '<ul style="padding-left:1.1rem;color:#475569;margin:0">'
                    '<li>Copy any error message exactly.</li><li>Say when it started.</li>'
                    '<li>Mention what you already tried.</li></ul></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Ticket lists (employee: mine, staff: assignments + queue, admin: all)
# ---------------------------------------------------------------------------
def ticket_list_view(mode):
    user = st.session_state.user
    heads = {
        "mine": ("My tickets", "Everything you have raised and where it stands."),
        "queue": ("Ticket queue" if user["role"] == "IT Staff" else "All tickets",
                  "Every ticket in the helpdesk. Open one to assign it, set a deadline or update its status."),
        "assignments": ("My assignments", "Tickets assigned to you, in the order you should work on them."),
    }
    page_header(*heads[mode])

    cols = st.columns([2.6, 1.3, 1.5, 1.5])
    search = cols[0].text_input("Search", placeholder="🔍  Search title, #ID or person",
                                label_visibility="collapsed", key=f"{mode}_q")
    priority = cols[1].selectbox("Priority", ["All"] + PRIORITIES, key=f"{mode}_prio",
                                 format_func=lambda p: p if p == "All" else f"{PRIORITY_DOT[p]} {p}",
                                 label_visibility="collapsed")
    assign_filter = "Everyone"
    if mode == "queue":
        assign_filter = cols[2].selectbox("Assignment", ["Everyone", "Unassigned", "Assigned to me"],
                                          key=f"{mode}_assign", label_visibility="collapsed")
    order_label = cols[3].selectbox("Sort", ["Priority & deadline", "Newest first"], key=f"{mode}_sort",
                                    label_visibility="collapsed")
    status = st.pills("Status", ["All"] + STATUSES, default="All", key=f"{mode}_status",
                      label_visibility="collapsed") or "All"
    include_done = True
    if mode == "assignments":
        include_done = st.toggle("Include completed tickets", value=False, key="asg_done")

    rows = fetch_tickets(
        user, status=status, search_text=search.strip() or None, priority=priority,
        assigned_to=user["user_id"] if (mode == "assignments" or assign_filter == "Assigned to me") else None,
        unassigned_only=assign_filter == "Unassigned",
        active_only=(mode == "assignments" and not include_done),
        order="newest" if order_label == "Newest first" else "priority",
    )
    overdue = sum(1 for r in rows if r["is_overdue"])
    st.caption(f"{len(rows)} ticket{'s' if len(rows) != 1 else ''}" + (f" · {overdue} overdue" if overdue else ""))

    if mode == "assignments" and rows and rows[0]["status"] in ("Open", "In Progress"):
        t = rows[0]
        st.markdown(f'<div class="nextup"><small>🔥 Next up · work on this first</small><b>#{t["ticket_id"]} · '
                    f'{esc(t["title"])}</b>{priority_chip(t["priority"])} {due_chip(t)}</div>',
                    unsafe_allow_html=True)
    ticket_cards(user, rows, f"list_{mode}", rank=(mode == "assignments" and order_label != "Newest first"))


# ---------------------------------------------------------------------------
# IT Staff home
# ---------------------------------------------------------------------------
def staff_home():
    user = st.session_state.user
    stats = get_dashboard_stats(user)
    hero("IT Staff workspace", f"{greeting()}, {esc(user['name'].split()[0])} 🛠️",
         "Work through your tickets by priority and deadline.")
    kpi_row([
        ("📌", "Assigned to me", stats["my_active"], "active tickets", "indigo"),
        ("⏰", "Due in 24 hours", stats["my_due_soon"], "needs attention soon", "amber"),
        ("⚠️", "Overdue", stats["my_overdue"], "past deadline", "red"),
        ("✅", "Completed by me", stats["my_done"], "resolved or closed", "green"),
        ("📥", "Waiting for an owner", stats["unassigned"], "unassigned in the queue", "blue"),
    ])
    st.write("")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### 🎯 Your next tickets")
        mine = fetch_tickets(user, assigned_to=user["user_id"], active_only=True)[:4]
        if mine:
            ticket_cards(user, mine, "stf_mine", rank=True)
        else:
            empty_state("☕", "You are all caught up", "Pick up a ticket from the waiting list.")
    with right:
        st.markdown("#### 📥 Waiting for someone to pick up")
        pool = fetch_tickets(user, unassigned_only=True, active_only=True)[:4]
        if pool:
            ticket_cards(user, pool, "stf_pool")
        else:
            empty_state("🙌", "Queue is empty", "Every ticket has an owner.")


# ---------------------------------------------------------------------------
# Admin: command center
# ---------------------------------------------------------------------------
def _plot(fig, key, height=300):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="DM Sans, sans-serif", color="#334155", size=13),
                      legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


def _donut(labels, values, colors, center, key):
    if not sum(values):
        empty_state("📭", "No data yet")
        return
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.66, sort=False, textinfo="value",
                           marker=dict(colors=colors, line=dict(color="white", width=3)),
                           hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"))
    fig.add_annotation(text=f"<b>{sum(values)}</b><br><span style='font-size:12px;color:#64748b'>{center}</span>",
                       showarrow=False, font=dict(size=26, color="#0f172a"))
    _plot(fig, key)


def _card_title(text):
    st.markdown(f'<div style="font-weight:800;color:#0f172a;margin:.2rem 0 .1rem">{text}</div>', unsafe_allow_html=True)


def admin_home():
    user = st.session_state.user
    head, btn = st.columns([6, 1], vertical_alignment="center")
    with head:
        hero("Admin command center", f"{greeting()}, {esc(user['name'].split()[0])} 🛡️",
             "How work is flowing through IT, and how the team is performing, right now.")
    with btn:
        st.button("Refresh", icon=":material/refresh:", width="stretch")

    ov = get_admin_overview()
    stats = get_dashboard_stats(user)
    sla = ov["sla"] or {}
    resolved_total = int(sla.get("resolved_total") or 0)
    sla_pct = round(100 * int(sla.get("on_time") or 0) / resolved_total) if resolved_total else 0
    avg_hours = float(sla.get("avg_hours") or 0)
    active = stats["open_count"] + stats["progress_count"]

    kpi_row([
        ("🎫", "Total tickets", stats["total"], "all time", "indigo"),
        ("🔧", "Active", active, "open or in progress", "violet"),
        ("📥", "Unassigned", stats["unassigned"], "need an owner", "blue" if not stats["unassigned"] else "amber"),
        ("⚠️", "Overdue", stats["overdue"], "past deadline", "red" if stats["overdue"] else "green"),
        ("⏱️", "Avg. resolution", f"{avg_hours:g}h", "from raised to resolved", "slate"),
    ])
    st.write("")

    status_counts = {r["status"]: int(r["total"]) for r in ov["status"]}
    prio_counts = {r["priority"]: int(r["total"]) for r in ov["priority"]}
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        with st.container(border=True):
            _card_title("Tickets by status")
            _donut(STATUSES, [status_counts.get(s, 0) for s in STATUSES],
                   [STATUS_COLORS[s] for s in STATUSES], "tickets", "pie_status")
    with c2:
        with st.container(border=True):
            _card_title("Tickets by priority")
            order = list(reversed(PRIORITIES))
            _donut(order, [prio_counts.get(p, 0) for p in order],
                   [PRIORITY_COLORS[p] for p in order], "tickets", "pie_priority")
    with c3:
        with st.container(border=True):
            _card_title("Deadlines met (SLA)")
            if resolved_total:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number", value=sla_pct, number=dict(suffix="%", font=dict(size=38)),
                    gauge=dict(axis=dict(range=[0, 100]), bar=dict(color="#6366f1", thickness=0.28),
                               steps=[dict(range=[0, 60], color="#fee2e2"), dict(range=[60, 85], color="#fef3c7"),
                                      dict(range=[85, 100], color="#dcfce7")])))
                _plot(fig, "gauge_sla")
                st.caption(f"{int(sla['on_time'])} of {resolved_total} resolved tickets finished by their deadline.")
            else:
                empty_state("⏳", "No resolved tickets yet")

    st.write("")
    c4, c5 = st.columns(2, gap="medium")
    staff = ov["staff"]
    with c4:
        with st.container(border=True):
            _card_title("Workload by team member")
            if staff:
                names = [s["name"] for s in staff]
                fig = go.Figure()
                for label, col, color in (("Open", "open_count", STATUS_COLORS["Open"]),
                                          ("In progress", "in_progress", STATUS_COLORS["In Progress"]),
                                          ("Completed", "resolved", STATUS_COLORS["Resolved"])):
                    fig.add_trace(go.Bar(y=names, x=[int(s[col]) for s in staff], name=label,
                                         orientation="h", marker_color=color))
                fig.update_layout(barmode="stack")
                fig.update_yaxes(autorange="reversed")
                fig.update_xaxes(gridcolor="#eef0f7")
                _plot(fig, "bar_staff")
            else:
                empty_state("👥", "No IT Staff yet", "Promote users on the Team page.")
    with c5:
        with st.container(border=True):
            _card_title("Tickets by category")
            if ov["category"]:
                cats = ov["category"]
                fig = go.Figure(go.Bar(y=[c["category_name"] for c in cats], x=[int(c["total"]) for c in cats],
                                       orientation="h", marker=dict(color="#818cf8"),
                                       text=[int(c["total"]) for c in cats], textposition="outside"))
                fig.update_yaxes(autorange="reversed")
                fig.update_xaxes(gridcolor="#eef0f7")
                _plot(fig, "bar_category")
            else:
                empty_state("📭", "No data yet")

    st.write("")
    c6, c7 = st.columns([1.7, 1], gap="medium")
    with c6:
        with st.container(border=True):
            _card_title("Last 14 days · raised vs resolved")
            days = [date.today() - timedelta(days=i) for i in range(13, -1, -1)]
            created = {r["day"]: int(r["total"]) for r in ov["created_by_day"]}
            solved = {r["day"]: int(r["total"]) for r in ov["resolved_by_day"]}
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=days, y=[created.get(d, 0) for d in days], name="Raised",
                                     mode="lines+markers", line=dict(color="#6366f1", width=3, shape="spline"),
                                     fill="tozeroy", fillcolor="rgba(99,102,241,.10)"))
            fig.add_trace(go.Scatter(x=days, y=[solved.get(d, 0) for d in days], name="Resolved",
                                     mode="lines+markers", line=dict(color="#10b981", width=3, shape="spline")))
            fig.update_xaxes(tickformat="%d %b", gridcolor="#eef0f7")
            fig.update_yaxes(gridcolor="#eef0f7", rangemode="tozero")
            _plot(fig, "trend", 300)
    with c7:
        with st.container(border=True):
            _card_title("Live activity")
            if ov["activity"]:
                rows = "".join(
                    f'<div class="event"><span class="dot"></span><b>{esc(a["actor"])}</b> {esc(a["event_text"])} '
                    f'<b>#{a["ticket_id"]}</b><br><span class="muted" style="margin-left:1.05rem">{fmt_dt(a["created_at"])}</span></div>'
                    for a in ov["activity"][:7])
                st.markdown(f'<div class="feed">{rows}</div>', unsafe_allow_html=True)
            else:
                empty_state("🕒", "No activity yet")

    st.write("")
    st.markdown("#### 👥 How the team is doing")
    if staff:
        cards = []
        for s in staff:
            assigned, done = int(s["assigned"]), int(s["resolved"])
            pct = round(100 * done / assigned) if assigned else 0
            avg = f'{float(s["avg_hours"]):g}h' if s["avg_hours"] is not None else "—"
            cards.append(
                f'<div class="tm"><div class="top">{avatar(s["name"], 42)}<div><b>{esc(s["name"])}</b><br>'
                f'<span class="muted">{ROLE_ICON[s["role"]]} {esc(s["role"])}</span></div></div>'
                f'<div class="bar"><i style="width:{pct}%"></i></div>'
                f'<div class="muted" style="margin-top:.3rem">{pct}% completed</div>'
                f'<div class="nums"><div><b>{assigned}</b><small>Assigned</small></div>'
                f'<div><b style="color:#059669">{done}</b><small>Completed</small></div>'
                f'<div><b style="color:{"#dc2626" if int(s["overdue"]) else "#0f172a"}">{int(s["overdue"])}</b><small>Overdue</small></div></div>'
                f'<div class="muted" style="text-align:center">Avg. resolution time: <b>{avg}</b></div></div>')
        st.markdown(f'<div class="team">{"".join(cards)}</div>', unsafe_allow_html=True)
    else:
        empty_state("👥", "No IT Staff yet")

    st.write("")
    st.markdown("#### 🚨 Needs attention")
    t_over, t_pool = st.tabs([f"⚠️ Overdue ({stats['overdue']})", f"📥 Unassigned ({stats['unassigned']})"])
    with t_over:
        rows = fetch_tickets(user, overdue_only=True)
        ticket_cards(user, rows, "adm_over", page_size=5)
    with t_pool:
        rows = fetch_tickets(user, unassigned_only=True, active_only=True)
        ticket_cards(user, rows, "adm_pool", page_size=5)


# ---------------------------------------------------------------------------
# Admin: team + SQL insights
# ---------------------------------------------------------------------------
def team_page():
    user = st.session_state.user
    page_header("Team & users", "Track performance and decide who is Employee, IT Staff or Admin.")
    tab_perf, tab_users = st.tabs(["📈 Performance", "👥 Users & roles"])
    with tab_perf:
        staff = get_admin_overview()["staff"]
        if staff:
            df = pd.DataFrame(staff)
            df["Completion"] = (df["resolved"].astype(float) / df["assigned"].replace(0, pd.NA).astype(float) * 100).fillna(0)
            df = df.rename(columns={"name": "Name", "role": "Role", "assigned": "Assigned", "open_count": "Open",
                                    "in_progress": "In progress", "resolved": "Completed", "overdue": "Overdue",
                                    "avg_hours": "Avg. hours"})
            st.dataframe(
                df[["Name", "Role", "Assigned", "Open", "In progress", "Completed", "Overdue", "Avg. hours", "Completion"]],
                hide_index=True, width="stretch",
                column_config={"Completion": st.column_config.ProgressColumn("Completion", min_value=0, max_value=100,
                                                                              format="%.0f%%")})
        else:
            empty_state("👥", "No IT Staff yet", "Promote a user in the next tab.")
    with tab_users:
        users = get_all_users()
        st.dataframe(pd.DataFrame(users).drop(columns=["user_id"]).rename(columns={
            "name": "Name", "email": "Email", "role": "Role", "created_at": "Joined", "tickets_raised": "Tickets raised"}),
            hide_index=True, width="stretch")
        with st.container(border=True):
            st.markdown("##### Change a role")
            st.caption("New people register as Employees. Promote someone to **IT Staff** so tickets can be assigned to them.")
            with st.form("role_form", border=False):
                c1, c2 = st.columns([2, 1])
                target = c1.selectbox("Person", users, format_func=lambda u: f"{u['name']} · {u['email']} ({u['role']})")
                new_role = c2.selectbox("New role", ["Employee", "IT Staff", "Admin"])
                go_btn = st.form_submit_button("Update role", type="primary", icon=":material/manage_accounts:")
            if go_btn:
                if target["user_id"] == user["user_id"]:
                    st.error("You cannot change your own role.")
                else:
                    set_user_role(target["user_id"], new_role)
                    flash(f"{target['name']} is now {new_role}.", "👥")
                    st.rerun()


def sql_insights_page():
    page_header("SQL insights", "Live reports calculated in MySQL with joins, subqueries and aggregate functions.")
    staff_workload, above_average, category_status, metrics = get_advanced_analytics()
    metrics = metrics or {}
    kpi_row([
        ("🎫", "Total tickets", int(metrics.get("total_tickets") or 0), "COUNT", "indigo"),
        ("🔴", "Critical", int(metrics.get("critical_tickets") or 0), "SUM(priority='Critical')", "red"),
        ("🟠", "High", int(metrics.get("high_tickets") or 0), "SUM(priority='High')", "amber"),
        ("🕒", "Avg. update gap", f"{metrics.get('avg_update_hours') or 0}h", "AVG + TIMESTAMPDIFF", "slate"),
    ])
    st.write("")
    t1, t2, t3, t4 = st.tabs(["Staff workload", "Above-average employees", "Category × status", "Concepts"])
    with t1:
        st.caption("LEFT JOIN, GROUP BY, COUNT and conditional SUM.")
        if staff_workload:
            st.dataframe(pd.DataFrame(staff_workload).drop(columns=["user_id"]).rename(columns={
                "staff_name": "Support staff", "assigned_tickets": "Assigned", "resolved_tickets": "Resolved",
                "active_tickets": "Active"}), hide_index=True, width="stretch")
        else:
            st.info("No IT Staff accounts or assigned tickets found.")
    with t2:
        st.caption("Nested subquery + GROUP BY + HAVING.")
        if above_average:
            st.dataframe(pd.DataFrame(above_average).drop(columns=["user_id"]).rename(columns={
                "name": "Employee", "email": "Email", "ticket_count": "Tickets"}), hide_index=True, width="stretch")
        else:
            st.info("No employee currently has ticket volume above the average.")
    with t3:
        st.caption("INNER JOIN with GROUP BY across two dimensions.")
        if category_status:
            st.dataframe(pd.DataFrame(category_status).rename(columns={
                "category_name": "Category", "status": "Status", "ticket_count": "Tickets"}),
                hide_index=True, width="stretch")
    with t4:
        st.markdown("""
- **Primary & foreign keys** connect users, tickets, categories, comments and ticket events.
- **INNER JOIN / LEFT JOIN** combine tickets with requester, assignee and category.
- **Aggregates** `COUNT`, `SUM`, `AVG`, `ROUND`, plus `TIMESTAMPDIFF` for resolution time.
- **GROUP BY / HAVING** summarise by status, priority, category and staff member.
- **Subqueries** compare each employee's volume with the average.
- **Indexes** speed up status, assignee, deadline and requester lookups.
- **Transactions** (`SELECT ... FOR UPDATE`) keep ticket edits and their history consistent.
""")


# ---------------------------------------------------------------------------
# Help page
# ---------------------------------------------------------------------------
def how_it_works_page():
    page_header("How it works", "Three roles, one shared ticket.")
    c1, c2, c3 = st.columns(3, gap="medium")
    roles = [
        (c1, "👤", "Employee", "Anyone in the company who has an IT problem.",
         ["Raise a ticket with a priority and description", "Follow its progress live", "Chat with the technician on the ticket"]),
        (c2, "🛠️", "IT Staff", "The technicians who fix problems.",
         ["Pick up unassigned tickets or receive them", "Work in priority + deadline order", "Update status, assign colleagues, comment"]),
        (c3, "🛡️", "Admin", "The IT manager who oversees everything.",
         ["Assign tickets and set deadlines", "Watch charts of workload and SLA", "Manage who is Employee, IT Staff or Admin"]),
    ]
    for col, icon, name, desc, points in roles:
        items = "".join(f"<li>{esc(p)}</li>" for p in points)
        col.markdown(f'<div class="lightcard" style="height:100%"><div style="font-size:1.8rem">{icon}</div>'
                     f'<h4>{name}</h4><p style="color:#64748b">{esc(desc)}</p>'
                     f'<ul style="padding-left:1.1rem;color:#475569">{items}</ul></div>', unsafe_allow_html=True)
    st.write("")
    st.markdown("#### The life of a ticket")
    demo = {"status": "In Progress", "assigned_to": 1}
    st.markdown(f'<div class="lightcard">{lifecycle_html(demo)}<p class="muted" style="text-align:center">'
                'Raised by an employee → assigned to IT Staff → worked on → resolved → closed</p></div>',
                unsafe_allow_html=True)
    st.write("")
    rows = "".join(f"<tr><td>{priority_chip(p)}</td><td>{esc(PRIORITY_HELP[p])}</td>"
                   f"<td><b>{human_minutes(SLA_HOURS[p] * 60)}</b></td></tr>" for p in reversed(PRIORITIES))
    st.markdown(f'<div class="lightcard"><h4>Priority and deadline targets</h4><table class="sla">'
                f'<tr><th>Priority</th><th>Meaning</th><th>Target</th></tr>{rows}</table>'
                f'<p class="muted" style="margin-top:.6rem">Every ticket gets a deadline from its priority when it is raised. '
                f'IT can adjust it. Tickets past their deadline show as <b>overdue</b>.</p></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Navigation + app shell
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Connecting to MySQL and preparing the helpdesk...")
def connect_and_prepare():
    initialize_database()
    seed_demo_data()
    return True


def build_pages(role):
    PAGES["help"] = st.Page(how_it_works_page, title="How it works", icon=":material/help:", url_path="how-it-works")
    if role == "Employee":
        PAGES["home"] = st.Page(employee_home, title="Home", icon=":material/home:", url_path="home", default=True)
        PAGES["new"] = st.Page(new_ticket_page, title="Raise a ticket", icon=":material/add_circle:", url_path="new-ticket")
        PAGES["mine"] = st.Page(lambda: ticket_list_view("mine"), title="My tickets",
                                icon=":material/confirmation_number:", url_path="my-tickets")
        return {"Workspace": [PAGES["home"], PAGES["new"], PAGES["mine"]], "Help": [PAGES["help"]]}
    if role == "IT Staff":
        PAGES["home"] = st.Page(staff_home, title="My workspace", icon=":material/dashboard:", url_path="workspace", default=True)
        PAGES["assign"] = st.Page(lambda: ticket_list_view("assignments"), title="My assignments",
                                  icon=":material/assignment_ind:", url_path="my-assignments")
        PAGES["queue"] = st.Page(lambda: ticket_list_view("queue"), title="Ticket queue",
                                 icon=":material/inbox:", url_path="queue")
        return {"Work": [PAGES["home"], PAGES["assign"], PAGES["queue"]], "Help": [PAGES["help"]]}
    PAGES["home"] = st.Page(admin_home, title="Command center", icon=":material/monitoring:", url_path="command-center", default=True)
    PAGES["queue"] = st.Page(lambda: ticket_list_view("queue"), title="All tickets",
                             icon=":material/inbox:", url_path="all-tickets")
    PAGES["team"] = st.Page(team_page, title="Team & users", icon=":material/groups:", url_path="team")
    PAGES["sql"] = st.Page(sql_insights_page, title="SQL insights", icon=":material/database:", url_path="sql-insights")
    return {"Oversight": [PAGES["home"], PAGES["queue"], PAGES["team"], PAGES["sql"]], "Help": [PAGES["help"]]}


def main():
    if "user" not in st.session_state:
        login_screen()
        return
    user = st.session_state.user
    nav = st.navigation(build_pages(user["role"]))
    with st.sidebar:
        st.markdown(f'<div class="profile">{avatar(user["name"], 42)}<div><div class="pname">{esc(user["name"])}</div>'
                    f'<div class="prole">{ROLE_ICON[user["role"]]} {esc(user["role"])}</div></div></div>',
                    unsafe_allow_html=True)
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            st.session_state.clear()
            st.rerun()
    pending = st.session_state.pop("_flash", None)
    if pending:
        st.toast(pending[0], icon=pending[1])
    nav.run()


if __name__ == "__main__":
    try:
        connect_and_prepare()
        main()
    except Error as exc:
        st.error("Could not connect to MySQL. Check the database settings and confirm MySQL Server is running.")
        with st.expander("Technical details"):
            st.code(str(exc))
        st.markdown("See **README.md** for database setup and configuration.")
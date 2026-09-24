"""Streamlit-Dashboard für ValuePulse.

Start über run.bat / run.sh oder direkt:
    streamlit run valuepulse/app.py
"""

from __future__ import annotations

import html
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from valuepulse.config import LOOKAHEAD_DAYS, load_settings, save_env_keys
from valuepulse.db import connect
from valuepulse.helptext import HELP_MARKDOWN
from valuepulse.model import OUTCOME_LABELS, decimal_de, pct
from valuepulse.models import DashboardData, MatchView
from valuepulse.monthcal import apply_day_click, month_weeks, shift_month, value_counts
from valuepulse.pipeline import run
from valuepulse.positions import STATUS_LABELS, add_position, list_positions, settle, summarize
from valuepulse.pro import build_pro_view
from valuepulse.providers import check_api_keys
from valuepulse.slip import STAKE_CAP, Slip, build_slip
from valuepulse.sports import SPORTS, sport_by_id

st.set_page_config(
    page_title="ValuePulse",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CSS = """
<style>
    html, body, [class*="css"] { font-size: 16px; }
    .stApp { background: #101214; color: #e8eef5; }
    [data-testid="stSidebar"] {
        background: #121316;
        border-right: 1px solid #2b2f36;
    }
    [data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
    [data-testid="stSidebar"] .stButton button,
    [data-testid="stSidebar"] [data-testid^="stBaseButton"] {
        justify-content: flex-start !important;
        text-align: left !important;
        border-radius: 12px;
        min-height: 2.7rem;
        padding: 0.55rem 0.9rem;
        line-height: 1.4;
        white-space: normal;
    }
    [data-testid="stSidebar"] .stButton button div,
    [data-testid="stSidebar"] .stButton button span,
    [data-testid="stSidebar"] .stButton button p {
        justify-content: flex-start !important;
        text-align: left !important;
        width: 100%;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary,
    [data-testid="stSidebar"] [data-testid="stExpander"] p {
        text-align: left !important;
        justify-content: flex-start !important;
    }
    [data-testid="stSidebar"] .stButton button[kind="secondary"] {
        background: transparent;
        border: 1px solid transparent;
        color: #d5dde6;
    }
    [data-testid="stMain"] .block-container {
        padding-top: 2.4rem;
        padding-bottom: 3.5rem;
        padding-left: 1.6rem;
        padding-right: 1.6rem;
        max-width: 1180px;
    }
    .vp-page-title {
        margin: 0 0 0.85rem;
        padding: 0.2rem 0.15rem 0.35rem 0;
        font-size: 1.7rem;
        font-weight: 700;
        line-height: 1.45;
        letter-spacing: 0;
        color: #f4f7fb;
        overflow: visible;
    }
    [data-testid="stSelectbox"] .react-aria-ComboBox > div {
        background: #2a3038 !important;
        border: 1px solid #9aa6b5 !important;
        border-radius: 10px !important;
        box-shadow: 0 0 0 1px rgba(154, 166, 181, 0.35);
    }
    [data-testid="stSelectbox"] .react-aria-ComboBox > div:focus-within,
    [data-testid="stSelectbox"] .react-aria-ComboBox > div[data-focus-within="true"] {
        border-color: #00e699 !important;
        box-shadow: 0 0 0 1px #00e699;
    }
    [data-testid="stSelectbox"] input {
        color: #f7fafc !important;
        font-weight: 600;
    }
    [data-testid="stSelectboxVirtualDropdown"] {
        background: #2a3038 !important;
        border: 1px solid #9aa6b5 !important;
        border-radius: 10px !important;
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.55) !important;
    }
    [data-testid="stSelectboxVirtualDropdown"] [data-hovered] [data-item-hl],
    [data-testid="stSelectboxVirtualDropdown"] [data-focused] [data-item-hl] {
        background: rgba(0, 230, 153, 0.22) !important;
    }
    .vp-brand {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        margin: 0 0 1rem;
        color: #f4f7fb;
        font-size: 1.25rem;
        font-weight: 750;
        line-height: 1.3;
    }
    .vp-logo {
        width: 2.1rem;
        height: 2.1rem;
        border-radius: 10px;
        background: #00e699;
        color: #06281c;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        letter-spacing: -0.03em;
    }
    h1, h2, h3, p, li, label, span { overflow: visible; }
    p, li, .stMarkdown p, .stMarkdown li { line-height: 1.55; }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {
        overflow: visible;
        white-space: normal;
        line-height: 1.35;
        height: auto;
    }
    [data-testid="stMetricValue"] { font-size: 1.45rem; padding-bottom: 0.15rem; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
        overflow-x: auto;
        overflow-y: visible;
        padding: 0.2rem 0 0.45rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: auto;
        min-height: 3rem;
        padding: 0.72rem 0.95rem;
        line-height: 1.45;
        white-space: nowrap;
    }
    .stTabs [data-baseweb="tab"] div {
        line-height: 1.45;
        overflow: visible;
        height: auto;
    }
    .vp-legend { display: flex; gap: 0.8rem; flex-wrap: wrap; margin: 0.3rem 0 0.9rem; }
    .vp-note { color: #c5d2e0; line-height: 1.5; margin: 0.2rem 0 0.8rem; }
    .vp-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        margin: 0.35rem 0 1rem;
        background: #1b1e22;
        border: 1px solid #2b2f36;
        border-radius: 12px;
        overflow: hidden;
    }
    .vp-table th, .vp-table td {
        text-align: left;
        padding: 0.85rem 0.95rem;
        line-height: 1.45;
        vertical-align: middle;
        border-bottom: 1px solid #2b2f36;
        white-space: normal;
        overflow: visible;
        color: #e8eef5;
    }
    .vp-table th {
        color: #b7c6d6;
        font-weight: 700;
        background: #121a24;
    }
    .vp-badge {
        display: inline-block;
        padding: 0.2rem 0.62rem 0.24rem;
        border-radius: 999px;
        line-height: 1.35;
        font-weight: 700;
        white-space: nowrap;
    }
    .vp-badge-green { background: #123d2a; color: #8ef0b5; }
    .vp-badge-yellow { background: #3d320f; color: #ffd56a; }
    .vp-badge-red { background: #3a2228; color: #ffb4b4; }
    .vp-card {
        border: 1px solid #2b2f36;
        border-left: 8px solid #8b98a8;
        border-radius: 12px;
        padding: 1.15rem 1.25rem 1.05rem;
        margin: 0 0 0.85rem;
        background: #1b1e22;
    }
    .vp-green { border-left-color: #00e699; }
    .vp-yellow { border-left-color: #f0c14a; }
    .vp-red { border-left-color: #e07a7a; background: #141c26; }
    .vp-kicker { color: #b7c6d6; font-size: 0.92rem; line-height: 1.45; margin-bottom: 0.2rem; }
    .vp-teams { font-size: 1.28rem; font-weight: 700; line-height: 1.35; color: #f4f7fb; }
    .vp-headline { margin-top: 0.45rem; font-size: 1.05rem; font-weight: 700; line-height: 1.45; }
    .vp-green .vp-headline { color: #8ef0b5; }
    .vp-yellow .vp-headline { color: #ffd56a; }
    .vp-red .vp-headline { color: #d5dee8; }
    .vp-explain { margin-top: 0.5rem; line-height: 1.6; color: #e8eef5; }
    .vp-meta { margin-top: 0.55rem; color: #c5d2e0; font-size: 0.95rem; line-height: 1.55; }
    .vp-foot { color: #9aabbc; font-size: 0.92rem; line-height: 1.5; margin-top: 1.3rem; }
    .vp-matrix td, .vp-matrix th { text-align: center; padding: 0.55rem 0.4rem; }
    .vp-slip-warn {
        background: #3d320f;
        color: #ffd56a;
        border: 1px solid #c9a227;
        border-radius: 12px;
        padding: 0.95rem 1.05rem;
        line-height: 1.55;
        margin: 0.2rem 0 1rem;
    }
    .vp-slip-warn strong { color: #ffe7a3; display: block; margin-bottom: 0.25rem; }
</style>
"""

_BADGE = {
    "green": ("vp-badge-green", "Grün"),
    "yellow": ("vp-badge-yellow", "Gelb"),
    "red": ("vp-badge-red", "Rot"),
}
_MODE_LABELS = {
    "live": "Live",
    "cache": "Gespeicherte Daten",
    "eingeschraenkt": "Live mit Lücken",
    "demo": "Demo",
}
_CHECK_TEXT = {
    "gültig": "gültig",
    "abgelehnt": "abgelehnt",
    "fehlt": "fehlt",
    "limit": "Limit erreicht, nicht abschließend geprüft",
    "nicht erreichbar": "nicht erreichbar",
}


@st.cache_data(ttl=600, show_spinner=False)
def _load(refresh_token: int, start_iso: str, end_iso: str) -> DashboardData:
    del refresh_token
    return run(date_from=date.fromisoformat(start_iso), date_to=date.fromisoformat(end_iso))


def _ensure_state() -> None:
    today = date.today()
    if "search_from" not in st.session_state:
        st.session_state.search_from = today
        st.session_state.search_to = today + timedelta(days=LOOKAHEAD_DAYS)
        st.session_state.vp_refresh = 0
    if "pick_start" not in st.session_state:
        st.session_state.pick_start = st.session_state.search_from
    if "pick_end" not in st.session_state:
        st.session_state.pick_end = st.session_state.search_to
    if "page" not in st.session_state:
        st.session_state.page = "dashboard"
    if "sport" not in st.session_state:
        st.session_state.sport = "football"
    if "cal_year" not in st.session_state:
        st.session_state.cal_year = today.year
        st.session_state.cal_month = today.month
        st.session_state.range_phase = "start"
    if "position_stake" not in st.session_state:
        st.session_state.position_stake = 1.0
    settings = load_settings()
    if "form_fd" not in st.session_state:
        st.session_state.form_fd = settings.football_key
    if "form_odds" not in st.session_state:
        st.session_state.form_odds = settings.odds_key


def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    _ensure_state()
    _sidebar()
    data = _data()
    page = st.session_state.page
    if page == "dashboard":
        _render_dashboard(data)
    elif page == "strategy":
        _render_strategy(data)
    elif page == "positions":
        _render_positions()
    elif page == "calendar":
        _render_calendar(data)
    elif page == "settings":
        _render_settings()
    else:
        _page_title("Hilfe")
        st.markdown(HELP_MARKDOWN)


def _sidebar() -> None:
    st.sidebar.markdown(
        '<div class="vp-brand"><span class="vp-logo">VP</span><span>ValuePulse</span></div>',
        unsafe_allow_html=True,
    )
    _nav("dashboard", "📊 Dashboard")
    with st.sidebar.expander("⚽ Sportarten", expanded=True):
        current = st.session_state.sport
        for sport in SPORTS:
            label = f"{sport.icon} {sport.name}"
            if st.button(
                label,
                key=f"sport-{sport.id}",
                type="primary" if sport.id == current else "secondary",
                width="stretch",
            ):
                st.session_state.sport = sport.id
                st.session_state.page = "dashboard"
                st.rerun()
    _nav("strategy", "📈 Strategie & Tippschein")
    _nav("positions", "💼 Positionen")
    _nav("calendar", "🗓️ Kalender")
    _nav("settings", "⚙️ Einstellungen")
    _nav("help", "❓ Hilfe")


def _nav(page: str, label: str) -> None:
    active = st.session_state.page == page
    if st.sidebar.button(label, key=f"nav-{page}", type="primary" if active else "secondary", width="stretch"):
        st.session_state.page = page
        st.rerun()


def _data() -> DashboardData:
    token = int(st.session_state.get("vp_refresh", 0))
    start = st.session_state.search_from.isoformat()
    end = st.session_state.search_to.isoformat()
    with st.spinner("Spiele und Quoten werden geladen …"):
        return _load(token, start, end)


def _render_dashboard(data: DashboardData) -> None:
    sport = sport_by_id(st.session_state.sport)
    _page_title(f"{sport.icon} {sport.name}")
    if not sport.live:
        st.info(
            f"{sport.name} ist vorbereitet ({sport.note}) "
            "Es werden noch keine Spiele abgefragt. Esports ist nicht enthalten. "
            "Fußball bleibt die aktive Quelle."
        )
        return
    period = _period_label()
    left, right = st.columns([4, 1])
    with left:
        st.markdown(f'<p class="vp-note">Berechnet für <b>{html.escape(period)}</b>. '
                    "Ein anderes Datum stellst du im Kalender ein und startest es dort extra.</p>",
                    unsafe_allow_html=True)
    with right:
        if st.button("Daten aktualisieren", type="primary", width="stretch"):
            st.session_state.vp_refresh = int(st.session_state.get("vp_refresh", 0)) + 1
            st.cache_data.clear()
            st.rerun()

    _banner(data)
    matches = data.matches
    value_count = sum(1 for match in matches if match.assessment.signal in {"green", "yellow"})
    c1, c2, c3 = st.columns(3)
    c1.metric("Spiele", len(matches))
    c2.metric("Value-Signale", value_count)
    c3.metric("Datenmodus", _MODE_LABELS.get(data.mode, data.mode))
    st.markdown(
        """
        <div class="vp-legend">
            <span class="vp-badge vp-badge-green">Grün · Value, gute Daten</span>
            <span class="vp-badge vp-badge-yellow">Gelb · Value, Daten dünn</span>
            <span class="vp-badge vp-badge-red">Rot · kein Vorteil</span>
        </div>
        <p class="vp-note">Hinweis: ValuePulse nutzt ein vereinfachtes Grundmodell. Ein berechneter Edge ersetzt keine eigene Spiel-Analyse.</p>
        """,
        unsafe_allow_html=True,
    )
    if data.warnings:
        with st.expander("Hinweise zum Datenabruf"):
            for warning in data.warnings:
                st.write(warning)
    if data.odds_requests_remaining is not None:
        st.caption(f"Verbleibende Abrufe bei The Odds API in diesem Monat: {data.odds_requests_remaining}")

    competitions = ["Alle Ligen"] + sorted({match.competition for match in matches})
    filter_col, value_col = st.columns([2, 1])
    with filter_col:
        competition = st.selectbox("Liga", competitions)
    with value_col:
        only_value = st.checkbox("Nur Value-Signale", value=False)
    st.number_input("Einsatz je Tipp (Einheiten)", min_value=0.1, step=0.5, key="position_stake")

    visible = _filter(matches, competition, only_value)
    if not visible:
        st.info("Im gewählten Filter liegen gerade keine Spiele.")
    else:
        st.markdown(_overview_table(visible), unsafe_allow_html=True)
        for match in visible:
            _card(match)
    st.markdown(
        '<p class="vp-foot">ValuePulse ist eine Rechenhilfe, keine Wettberatung. '
        "Ein Edge ist keine Gewinnzusage. Quoten ändern sich.</p>",
        unsafe_allow_html=True,
    )


def _render_calendar(data: DashboardData) -> None:
    _page_title("Sportkalender")
    st.markdown(
        '<p class="vp-note">Ein Klick auf einen Tag setzt nur den Zeitraum. '
        "Die Analyse startet erst mit <b>Spiele für gewählten Zeitraum berechnen</b>. "
        "Grüne Zahlen sind Value-Signale im zuletzt berechneten Fenster.</p>",
        unsafe_allow_html=True,
    )
    year = int(st.session_state.cal_year)
    month = int(st.session_state.cal_month)
    prev_col, title_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button("←", key="cal-prev"):
            st.session_state.cal_year, st.session_state.cal_month = shift_month(year, month, -1)
            st.rerun()
    with title_col:
        st.markdown(
            f'<p class="vp-page-title">{html.escape(calendar_title(year, month))}</p>',
            unsafe_allow_html=True,
        )
    with next_col:
        if st.button("→", key="cal-next"):
            st.session_state.cal_year, st.session_state.cal_month = shift_month(year, month, 1)
            st.rerun()
    counts = value_counts(data.matches, year, month)
    weekday_row = st.columns(7)
    for index, name in enumerate(("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")):
        weekday_row[index].caption(name)
    for week in month_weeks(year, month):
        cells = st.columns(7)
        for index, day in enumerate(week):
            with cells[index]:
                if day is None:
                    st.write("")
                    continue
                mark = counts.get(day, 0)
                label = str(day.day) if mark == 0 else f"{day.day} · {mark}"
                if st.button(label, key=f"day-{day.isoformat()}"):
                    start, end, phase = apply_day_click(
                        st.session_state.get("pick_start"),
                        str(st.session_state.get("range_phase", "start")),
                        day,
                    )
                    st.session_state.pick_start = start
                    st.session_state.pick_end = end
                    st.session_state.range_phase = phase
                    st.rerun()
    start_col, end_col = st.columns(2)
    with start_col:
        st.date_input("Startdatum", key="pick_start", format="DD.MM.YYYY")
    with end_col:
        st.date_input("Enddatum", key="pick_end", format="DD.MM.YYYY")
    st.caption(f"Zuletzt berechnet: {_period_label()}. Der Klick oben hat noch nichts neu geladen.")
    if st.button("Spiele für gewählten Zeitraum berechnen", type="primary"):
        _commit_range()


def calendar_title(year: int, month: int) -> str:
    names = (
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember",
    )
    return f"{names[month - 1]} {year}"


def _commit_range() -> None:
    start = st.session_state.pick_start
    end = st.session_state.pick_end
    if end < start:
        st.error("Das Enddatum liegt vor dem Startdatum. Bitte die Tage tauschen.")
        return
    if (end - start).days > 31:
        st.error("Bitte höchstens 31 Tage auf einmal wählen, damit die API-Kontingente reichen.")
        return
    st.session_state.search_from = start
    st.session_state.search_to = end
    st.session_state.vp_refresh = int(st.session_state.get("vp_refresh", 0)) + 1
    st.session_state.range_phase = "start"
    st.cache_data.clear()
    st.rerun()


def _render_settings() -> None:
    _page_title("API-Schlüssel")
    st.markdown(
        '<p class="vp-note">Die Schlüssel bleiben auf diesem Rechner in der Datei <b>.env</b>. '
        "Ohne gültige Schlüssel läuft der Demo-Modus.</p>",
        unsafe_allow_html=True,
    )
    current = load_settings()
    if current.has_live_keys:
        st.success("Beide Schlüssel sind gespeichert. Ob sie gültig sind, steht nach dem Speichern darunter.")
    else:
        st.warning("Demo-Modus ist aktiv. Es fehlt mindestens ein Schlüssel.")
    if st.session_state.get("key_status"):
        st.info(st.session_state.key_status)

    st.text_input("Football-Data API Key", type="password", key="form_fd")
    st.text_input("The Odds API Key", type="password", key="form_odds")
    st.caption("Kostenlose Schlüssel: football-data.org und the-odds-api.com.")
    if st.button("Schlüssel lokal speichern", type="primary"):
        football = str(st.session_state.get("form_fd", "")).strip()
        odds = str(st.session_state.get("form_odds", "")).strip()
        save_env_keys(football, odds)
        st.cache_data.clear()
        try:
            checked = check_api_keys(football, odds)
            st.session_state.key_status = _key_message(checked)
        except Exception:
            st.session_state.key_status = (
                "Die Schlüssel wurden gespeichert. Die Prüfung war gerade nicht möglich."
            )
        st.rerun()


def _render_strategy(data: DashboardData) -> None:
    _page_title("Strategie & Tippschein")
    choice = st.radio("Ansicht", ["Tippschein", "Pro"], horizontal=True)
    scoped = data
    if st.session_state.sport != "football":
        scoped = DashboardData(mode=data.mode, banner=data.banner, matches=[])
    if choice == "Pro":
        _render_pro(scoped)
    else:
        _render_slip(scoped)


def _render_positions() -> None:
    _page_title("Positionen")
    st.markdown(
        '<p class="vp-note">Hier siehst du, ob die gespeicherten Tipps aufgegangen sind. '
        "Neue Tipps kommen über den Button am Spiel im Dashboard.</p>",
        unsafe_allow_html=True,
    )
    settings = load_settings()
    conn = connect(settings.db_path)
    try:
        rows = list_positions(conn)
        summary = summarize(rows)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gesamt G&V", _units(summary.pnl))
        rate = "—" if summary.win_rate is None else pct(summary.win_rate, 1)
        c2.metric("Gewinnrate", f"{rate} | {summary.wins}W - {summary.losses}L")
        c3.metric("Aktive Positionen", str(summary.open_count))
        roi = "—" if summary.roi is None else pct(summary.roi, 1)
        c4.metric("ROI / Yield", roi)
        open_rows = [row for row in rows if row.status == "open"]
        if open_rows:
            labels = [f"#{row.id} {row.match_label} · {row.pick_label}" for row in open_rows]
            picked = st.selectbox("Offene Position", labels)
            result = st.radio("Ergebnis nach dem Spiel", ["Gewonnen", "Verloren", "Storniert"], horizontal=True)
            if st.button("Ergebnis speichern", type="primary"):
                status = {"Gewonnen": "won", "Verloren": "lost", "Storniert": "void"}[result]
                settle(conn, open_rows[labels.index(picked)].id, status)
                st.rerun()
        if not rows:
            st.info("Noch keine Position. Im Dashboard bei einem Spiel auf „Tipp zu Positionen hinzufügen“ klicken.")
        else:
            table = [
                {
                    "Datum": row.created_at[:10],
                    "Sportart": _sport_name(row.sport),
                    "Liga": row.competition,
                    "Match": row.match_label,
                    "Tipp": row.pick_label,
                    "Quote": decimal_de(row.odds),
                    "Modell": pct(row.probability, 1),
                    "Einsatz": _units(row.stake).replace("+", ""),
                    "Ergebnis": _status_mark(row.status),
                }
                for row in rows
            ]
            st.markdown(_html_table(pd.DataFrame(table)), unsafe_allow_html=True)
    finally:
        conn.close()


def _page_title(text: str) -> None:
    st.markdown(f'<p class="vp-page-title">{html.escape(text)}</p>', unsafe_allow_html=True)


def _units(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f} Einheiten".replace(".", ",")


def _sport_name(sport_id: str) -> str:
    try:
        return sport_by_id(sport_id).name
    except ValueError:
        return sport_id


def _status_mark(status: str) -> str:
    marks = {"open": "⏳", "won": "🟢", "lost": "🔴", "void": "🟡"}
    return f"{marks.get(status, '')} {STATUS_LABELS.get(status, status)}"


def _render_slip(data: DashboardData) -> None:
    _page_title("Tippschein-Generator")
    st.markdown(
        '<p class="vp-note">Aus den Value-Signalen mit mehr als 3 % Edge wird ein Schein gebaut. '
        "Dieselbe Mannschaft kommt nur einmal vor. Der Button rechnet den Schein, "
        "die Regler allein noch nicht.</p>",
        unsafe_allow_html=True,
    )
    count_col, risk_col = st.columns([1, 2])
    with count_col:
        count = st.selectbox("Anzahl der Spiele", list(range(2, 11)), index=1)
    with risk_col:
        risk_choice = st.radio(
            "Risikostufe",
            [
                "🛡️ Wenig Risiko",
                "⚖️ Mittel (Standard)",
                "🚀 Hoch (Risiko)",
            ],
            index=1,
        )
    risk = {
        "🛡️ Wenig Risiko": "wenig",
        "⚖️ Mittel (Standard)": "mittel",
        "🚀 Hoch (Risiko)": "hoch",
    }[risk_choice]
    st.caption(
        "Wenig Risiko: Trefferchance ab 55 % und Datenqualität ab 60. "
        "Mittel: bestes Produkt aus Edge und Trefferchance. "
        "Hoch: größter Edge, auch bei hoher Quote. "
        f"Der Gesamteinsatz ist ein Viertel-Kelly und höchstens {pct(STAKE_CAP[risk], 1)} der Bankroll."
    )
    fingerprint = tuple(
        (
            match.competition,
            match.home,
            match.away,
            match.kickoff.isoformat(),
            match.assessment.pick,
            round(match.assessment.edge, 5),
            match.assessment.quality,
        )
        for match in data.matches
    )
    if st.button("Tippschein generieren", type="primary"):
        st.session_state.slip_result = build_slip(data.matches, count=int(count), risk=risk)
        st.session_state.slip_fingerprint = fingerprint
    slip = st.session_state.get("slip_result")
    if not isinstance(slip, Slip):
        st.info("Noch kein Schein. Anzahl und Risiko einstellen, dann auf Tippschein generieren.")
        return
    if st.session_state.get("slip_fingerprint") != fingerprint:
        st.info("Die berechneten Spiele haben sich geändert. Bitte den Tippschein neu generieren.")
        return
    if slip.requested != int(count) or slip.risk != risk:
        st.caption("Die Einstellung oben ist noch nicht im Schein. Dafür erneut auf Tippschein generieren.")
    _show_slip(slip)


def _show_slip(slip: Slip) -> None:
    if slip.warning:
        title, _, body = slip.warning.partition("\n")
        st.markdown(
            f'<div class="vp-slip-warn"><strong>⚠️ {html.escape(title)}</strong>'
            f"{html.escape(body)}</div>",
            unsafe_allow_html=True,
        )
    if not slip.legs:
        st.info("Für diese Risikostufe liegt gerade kein qualifiziertes Spiel vor.")
        st.text_area("Schein zum Kopieren", value=slip.copy_text, height=140, key=_copy_key(slip))
        return
    rows = [
        {
            "Liga": leg.competition,
            "Paarung": f"{leg.home} – {leg.away}",
            "Tipp": leg.pick_label,
            "Einzelquote": decimal_de(leg.odds),
            "Modell": pct(leg.probability, 1),
        }
        for leg in slip.legs
    ]
    st.markdown(_html_table(pd.DataFrame(rows)), unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Gesamtquote", decimal_de(slip.combined_odds or 0.0))
    c2.metric("Gesamt-Wahrscheinlichkeit", pct(slip.combined_probability or 0.0))
    c3.metric("Empfohlener Gesamteinsatz", pct(slip.stake))
    cap_note = (
        f" Der Viertel-Kelly läge höher und ist auf {pct(slip.stake_cap, 1)} gedeckelt."
        if slip.stake_capped
        else ""
    )
    st.caption(
        f"{slip.risk_label}: {len(slip.legs)} von {slip.requested} Spielen. "
        "Gesamtquote und Gesamt-Wahrscheinlichkeit sind das Produkt der Einzelwerte."
        f"{cap_note} Keine Wettberatung."
    )
    st.text_area("Schein zum Kopieren", value=slip.copy_text, height=220, key=_copy_key(slip))


def _copy_key(slip: Slip) -> str:
    return "slip-copy-" + str(abs(hash(slip.copy_text)))


def _render_pro(data: DashboardData) -> None:
    _page_title("Erweiterte Metriken")
    st.markdown(
        '<p class="vp-note">Poisson-Matrix, Buchmacher-Marge, faire Quoten nach Shin und Power, '
        "sowie ein Viertel-Kelly als empfohlener Höchsteinsatz. Das ist keine Einsatz-Anweisung.</p>",
        unsafe_allow_html=True,
    )
    if not data.matches:
        st.info("Für den gewählten Zeitraum liegen keine Spiele vor.")
        return
    labels = [f"{match.home} – {match.away} ({match.kickoff_label})" for match in data.matches]
    choice = st.selectbox("Spiel", labels)
    match = data.matches[labels.index(choice)]
    view = build_pro_view(match.assessment)
    item = match.assessment
    c1, c2, c3 = st.columns(3)
    c1.metric("Marge der besten Quoten", pct(view.margin))
    c2.metric(f"Edge {item.pick_label}", pct(item.edge))
    c3.metric("Empfohlener Max-Einsatz", pct(view.recommended_stake[item.pick]))
    if view.margin < 0:
        st.caption(
            "Eine negative Marge heißt: die besten Preise ergeben zusammen weniger als 100 %. "
            "Shin und Power rechnen sie trotzdem auf 100 % um."
        )
    if view.recommended_stake[item.pick] <= 0:
        st.caption("Empfohlener Max-Einsatz: 0 %. Der Viertel-Kelly sieht hier keinen Einsatz.")
    else:
        st.caption(
            f"Empfohlener Max-Einsatz: {pct(view.recommended_stake[item.pick])} des Budgets "
            f"auf {item.pick_label} bei Quote {decimal_de(item.odds[item.pick])}. "
            "Das ist ein Viertel des vollen Kelly-Anteils."
        )
    st.markdown(_pro_table(item, view), unsafe_allow_html=True)
    st.markdown("**Poisson-Matrix** · Wahrscheinlichkeit je Spielstand")
    if not view.matrix:
        st.info("Für dieses Spiel fehlen erwartete Tore, deshalb gibt es keine Matrix.")
        return
    st.markdown(_matrix_table(view.matrix), unsafe_allow_html=True)
    st.caption(
        f"Die Felder 0:0 bis 5:5 decken {pct(view.matrix_mass, 0)} ab. "
        "Höhere Spielstände stecken im Rest des Modells."
    )


def _key_message(checked: dict[str, str]) -> str:
    football = _CHECK_TEXT.get(checked.get("football", ""), "ungeprüft")
    odds = _CHECK_TEXT.get(checked.get("odds", ""), "ungeprüft")
    if checked.get("football") == "gültig" and checked.get("odds") == "gültig":
        return (
            "Beide Schlüssel sind gültig. Der Demo-Modus ist aus. "
            "Im Dashboard auf „Daten aktualisieren“ oder im Kalender auf „Spiele suchen & berechnen“ klicken."
        )
    if "fehlt" in (checked.get("football"), checked.get("odds")):
        return "Gespeichert. Der Demo-Modus bleibt aktiv, weil mindestens ein Schlüssel fehlt."
    return f"Gespeichert. Football-Data: {football}. The Odds API: {odds}."


def _period_label() -> str:
    start = st.session_state.search_from.strftime("%d.%m.%Y")
    end = st.session_state.search_to.strftime("%d.%m.%Y")
    return f"{start} bis {end}"


def _banner(data: DashboardData) -> None:
    if data.mode == "live":
        st.success(data.banner)
    else:
        st.warning(data.banner)


def _filter(matches: list[MatchView], competition: str, only_value: bool) -> list[MatchView]:
    visible = matches
    if competition != "Alle Ligen":
        visible = [match for match in visible if match.competition == competition]
    if only_value:
        visible = [match for match in visible if match.assessment.signal in {"green", "yellow"}]
    return visible


def _badge(signal: str) -> str:
    css, label = _BADGE[signal]
    return f'<span class="vp-badge {css}">{label}</span>'


def _overview_table(matches: list[MatchView]) -> str:
    frame = pd.DataFrame(
        [
            {
                "Ampel": _badge(match.assessment.signal),
                "Spiel": f"{match.home} – {match.away}",
                "Liga": match.competition,
                "Anpfiff": match.kickoff_label,
                "Edge": pct(match.assessment.edge),
                "Qualität": f"{match.assessment.quality} %",
            }
            for match in matches
        ]
    )
    return _html_table(frame, raw_html={"Ampel"})


def _pro_table(item, view) -> str:
    rows = []
    for key in ("home", "draw", "away"):
        rows.append(
            {
                "Ausgang": OUTCOME_LABELS[key],
                "Modell": pct(item.model_probs[key], 0),
                "Quote": decimal_de(item.odds[key]),
                "Roh": pct(1.0 / item.odds[key], 0),
                "Shin": pct(view.shin[key], 0),
                "Power": pct(view.power[key], 0),
                "Edge roh": pct(view.edge_raw[key]),
                "Edge Shin": pct(view.edge_shin[key]),
                "Max-Einsatz": pct(view.recommended_stake[key]),
            }
        )
    return _html_table(pd.DataFrame(rows))


def _matrix_table(matrix: list[list[float]]) -> str:
    columns = [f"Gast {goals}" for goals in range(len(matrix[0]))]
    rows = []
    for home_goals, row in enumerate(matrix):
        record = {"Heim": f"{home_goals}"}
        for away_goals, probability in enumerate(row):
            record[columns[away_goals]] = pct(probability, 1)
        rows.append(record)
    return _html_table(pd.DataFrame(rows), extra_class="vp-matrix")


def _html_table(frame: pd.DataFrame, raw_html: set[str] | None = None, extra_class: str = "") -> str:
    raw_html = raw_html or set()
    header = "".join(f"<th>{html.escape(str(column))}</th>" for column in frame.columns)
    body: list[str] = []
    for _, row in frame.iterrows():
        cells = []
        for column, value in row.items():
            text = str(value)
            if column not in raw_html:
                text = html.escape(text)
            cells.append(f"<td>{text}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    css = "vp-table " + extra_class
    return (
        f'<table class="{css.strip()}"><thead><tr>{header}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _card(match: MatchView) -> None:
    item = match.assessment
    probs = " · ".join(
        f"{label} {pct(item.model_probs[key], 0)}"
        for key, label in (("home", "Heimsieg"), ("draw", "Unentschieden"), ("away", "Auswärtssieg"))
    )
    odds = " · ".join(
        f"{label} {decimal_de(item.odds[key])}"
        for key, label in (("home", "Heimsieg"), ("draw", "Unentschieden"), ("away", "Auswärtssieg"))
    )
    body = f"""
    <div class="vp-card vp-{item.signal}">
        <div class="vp-kicker">{html.escape(match.competition)} · {html.escape(match.kickoff_label)}</div>
        <div class="vp-teams">{html.escape(match.home)} – {html.escape(match.away)}</div>
        <div class="vp-headline">{_badge(item.signal)} {html.escape(item.headline)}</div>
        <div class="vp-explain">{html.escape(item.explanation)}</div>
        <div class="vp-meta">Modell: {html.escape(probs)}<br>Beste Quoten: {html.escape(odds)} · Datenqualität {item.quality} %</div>
    </div>
    """
    st.markdown(body, unsafe_allow_html=True)
    key = f"pos-{match.home}-{match.away}-{match.kickoff.isoformat()}"
    if st.button("+ Tipp zu Positionen hinzufügen", key=key):
        _save_position(match)


def _save_position(match: MatchView) -> None:
    item = match.assessment
    settings = load_settings()
    conn = connect(settings.db_path)
    try:
        add_position(
            conn,
            sport=str(st.session_state.sport),
            competition=match.competition,
            match_label=f"{match.home} – {match.away}",
            kickoff=match.kickoff.isoformat(),
            pick_label=item.pick_label,
            odds=float(item.odds[item.pick]),
            probability=float(item.model_probs[item.pick]),
            stake=float(st.session_state.position_stake),
        )
    finally:
        conn.close()
    st.success(f"{match.home} – {match.away} liegt jetzt unter Positionen.")


main()

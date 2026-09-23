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
from valuepulse.helptext import HELP_MARKDOWN
from valuepulse.model import OUTCOME_LABELS, decimal_de, pct
from valuepulse.models import DashboardData, MatchView
from valuepulse.pipeline import run
from valuepulse.pro import build_pro_view
from valuepulse.providers import check_api_keys

st.set_page_config(
    page_title="ValuePulse",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_CSS = """
<style>
    html, body, [class*="css"] { font-size: 16px; }
    .stApp { background: #0e141b; color: #e8eef5; }
    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 3.5rem;
        max-width: 1180px;
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
        background: #17202b;
        border-radius: 12px;
        overflow: hidden;
    }
    .vp-table th, .vp-table td {
        text-align: left;
        padding: 0.78rem 0.9rem;
        line-height: 1.45;
        vertical-align: middle;
        border-bottom: 1px solid #2c3a4b;
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
        border: 1px solid #2c3a4b;
        border-left: 8px solid #8b98a8;
        border-radius: 14px;
        padding: 1.05rem 1.15rem 1rem;
        margin: 0 0 0.85rem;
        background: #17202b;
    }
    .vp-green { border-left-color: #3ddc97; }
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
    settings = load_settings()
    if "form_fd" not in st.session_state:
        st.session_state.form_fd = settings.football_key
    if "form_odds" not in st.session_state:
        st.session_state.form_odds = settings.odds_key


def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    _ensure_state()
    st.title("ValuePulse")
    st.caption("Modell gegen Buchmacher. Ein Value-Signal beginnt bei einem Edge über 3 %.")

    dashboard, calendar, settings, pro, help_tab = st.tabs(
        [
            "📊 Dashboard (Live & Signale)",
            "🗓️ Datums-Filter (Kalender)",
            "⚙️ Einstellungen (API-Keys)",
            "💎 Pro-Version (Erweiterte Metriken)",
            "❓ Hilfe & Anleitung",
        ]
    )
    data = _data()
    with dashboard:
        _render_dashboard(data)
    with calendar:
        _render_calendar()
    with settings:
        _render_settings()
    with pro:
        _render_pro(data)
    with help_tab:
        st.markdown(HELP_MARKDOWN)


def _data() -> DashboardData:
    token = int(st.session_state.get("vp_refresh", 0))
    start = st.session_state.search_from.isoformat()
    end = st.session_state.search_to.isoformat()
    with st.spinner("Spiele und Quoten werden geladen …"):
        return _load(token, start, end)


def _render_dashboard(data: DashboardData) -> None:
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


def _render_calendar() -> None:
    st.subheader("Zeitraum wählen")
    st.markdown(
        '<p class="vp-note">Die Auswahl im Kalender startet <b>keine</b> Berechnung. '
        "Erst der Button darunter holt die Spiele und rechnet die Signale.</p>",
        unsafe_allow_html=True,
    )
    start_col, end_col = st.columns(2)
    with start_col:
        st.date_input("Startdatum", key="pick_start", format="DD.MM.YYYY")
    with end_col:
        st.date_input("Enddatum", key="pick_end", format="DD.MM.YYYY")
    st.caption(f"Zuletzt berechnet: {_period_label()}.")
    if st.button("Spiele suchen & berechnen", type="primary"):
        start = st.session_state.pick_start
        end = st.session_state.pick_end
        if end < start:
            st.error("Das Enddatum liegt vor dem Startdatum. Bitte die Tage tauschen.")
        elif (end - start).days > 31:
            st.error("Bitte höchstens 31 Tage auf einmal wählen, damit die API-Kontingente reichen.")
        else:
            st.session_state.search_from = start
            st.session_state.search_to = end
            st.session_state.vp_refresh = int(st.session_state.get("vp_refresh", 0)) + 1
            st.cache_data.clear()
            st.rerun()


def _render_settings() -> None:
    st.subheader("API-Schlüssel")
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


def _render_pro(data: DashboardData) -> None:
    st.subheader("Erweiterte Metriken")
    st.markdown(
        '<p class="vp-note">Poisson-Matrix, Buchmacher-Marge, faire Quoten nach Shin und Power, '
        "sowie der volle Kelly-Anteil. Das ist eine Rechenhilfe, keine Einsatz-Anweisung.</p>",
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
    c3.metric(f"Kelly {item.pick_label}", pct(view.kelly[item.pick]))
    if view.margin < 0:
        st.caption(
            "Eine negative Marge heißt: die besten Preise ergeben zusammen weniger als 100 %. "
            "Shin und Power rechnen sie trotzdem auf 100 % um."
        )
    if view.kelly[item.pick] <= 0:
        st.caption("Der Kelly-Anteil ist 0 %. Das Kriterium sieht hier keinen Einsatz.")
    else:
        st.caption(
            f"Voller Kelly-Anteil: {pct(view.kelly[item.pick])} des Budgets auf {item.pick_label} "
            f"bei Quote {decimal_de(item.odds[item.pick])}. Viele nutzen nur einen Teil davon."
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
                "Kelly": pct(view.kelly[key]),
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


main()

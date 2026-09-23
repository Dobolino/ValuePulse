"""Streamlit-Dashboard für ValuePulse.

Start über run.bat / run.sh oder direkt:
    streamlit run valuepulse/app.py
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from valuepulse.helptext import HELP_MARKDOWN
from valuepulse.model import decimal_de, pct
from valuepulse.models import DashboardData, MatchView
from valuepulse.pipeline import run

st.set_page_config(
    page_title="ValuePulse",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_CSS = """
<style>
    .block-container { padding-top: 1.4rem; max-width: 980px; }
    .vp-legend { display: flex; gap: 1.2rem; flex-wrap: wrap; margin: 0.2rem 0 0.8rem; }
    .vp-legend span { font-size: 0.92rem; color: #3d4654; }
    .vp-card {
        border: 1px solid #e3e7ee;
        border-left: 8px solid #9aa3b2;
        border-radius: 14px;
        padding: 0.95rem 1.05rem 0.85rem;
        margin-bottom: 0.75rem;
        background: #ffffff;
    }
    .vp-green { border-left-color: #1f8a4c; }
    .vp-yellow { border-left-color: #d39b12; }
    .vp-red { border-left-color: #c45c5c; background: #fbfbfc; }
    .vp-kicker { color: #5c6778; font-size: 0.85rem; margin-bottom: 0.15rem; }
    .vp-teams { font-size: 1.25rem; font-weight: 700; color: #1c2430; }
    .vp-headline { margin-top: 0.35rem; font-size: 1.05rem; font-weight: 650; }
    .vp-green .vp-headline { color: #146c3a; }
    .vp-yellow .vp-headline { color: #8a6408; }
    .vp-red .vp-headline { color: #6d727c; }
    .vp-explain { margin-top: 0.45rem; line-height: 1.45; color: #243040; }
    .vp-meta { margin-top: 0.45rem; color: #5c6778; font-size: 0.88rem; }
    .vp-foot { color: #6b7280; font-size: 0.85rem; margin-top: 1.2rem; }
</style>
"""

_ICONS = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
_MODE_LABELS = {
    "live": "Live",
    "cache": "Gespeicherte Daten",
    "eingeschraenkt": "Live mit Lücken",
    "demo": "Demo",
}


@st.cache_data(ttl=600, show_spinner=False)
def _load(refresh_token: int) -> DashboardData:
    del refresh_token
    return run()


def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    dashboard_tab, help_tab = st.tabs(["Dashboard", "Hilfe"])
    with help_tab:
        st.markdown(HELP_MARKDOWN)
    with dashboard_tab:
        _render_dashboard()


def _render_dashboard() -> None:
    title_col, button_col = st.columns([4, 1])
    with title_col:
        st.title("ValuePulse")
        st.caption("Modell-Wahrscheinlichkeit gegen Buchmacher-Quote. Value ab einem Edge über 3 %.")
    with button_col:
        st.write("")
        st.write("")
        if st.button("Daten aktualisieren", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.session_state["vp_refresh"] = st.session_state.get("vp_refresh", 0) + 1
            st.rerun()

    token = st.session_state.get("vp_refresh", 0)
    with st.spinner("Spiele und Quoten werden geladen …"):
        data = _load(token)

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
            <span>🟢 Value, gute Daten</span>
            <span>🟡 Value, Datenqualität verringert</span>
            <span>🔴 Kein Vorteil gegenüber dem Buchmacher</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if data.warnings:
        with st.expander("Hinweise zum Datenabruf"):
            for warning in data.warnings:
                st.write("• " + warning)
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
        st.dataframe(_table(visible), use_container_width=True, hide_index=True)
        for match in visible:
            _card(match)

    st.markdown(
        '<p class="vp-foot">ValuePulse ist eine Rechenhilfe, keine Wettberatung. '
        "Ein Edge ist keine Gewinnzusage. Quoten ändern sich.</p>",
        unsafe_allow_html=True,
    )


def _banner(data: DashboardData) -> None:
    if data.mode == "live":
        st.success(data.banner)
    elif data.mode == "demo":
        st.warning(data.banner)
    else:
        st.warning(data.banner)


def _filter(matches: list[MatchView], competition: str, only_value: bool) -> list[MatchView]:
    visible = matches
    if competition != "Alle Ligen":
        visible = [match for match in visible if match.competition == competition]
    if only_value:
        visible = [match for match in visible if match.assessment.signal in {"green", "yellow"}]
    return visible


def _table(matches: list[MatchView]) -> pd.DataFrame:
    rows = []
    for match in matches:
        item = match.assessment
        rows.append(
            {
                "Ampel": _ICONS[item.signal],
                "Spiel": f"{match.home} – {match.away}",
                "Liga": match.competition,
                "Anpfiff": match.kickoff_label,
                "Signal": item.headline,
                "Edge": pct(item.edge),
                "Qualität": f"{item.quality} %",
            }
        )
    return pd.DataFrame(rows)


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
        <div class="vp-headline">{_ICONS[item.signal]} {html.escape(item.headline)}</div>
        <div class="vp-explain">{html.escape(item.explanation)}</div>
        <div class="vp-meta">Modell: {html.escape(probs)}<br>Beste Quoten: {html.escape(odds)} · Datenqualität {item.quality} %</div>
    </div>
    """
    st.markdown(body, unsafe_allow_html=True)


main()

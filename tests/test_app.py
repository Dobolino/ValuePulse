"""Exercise the Streamlit UI without network access or real user data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dataclasses import replace

from streamlit.testing.v1 import AppTest
from valuepulse.models import DashboardData
from tests.test_slip import _match

APP=Path(__file__).resolve().parents[1]/'valuepulse'/'app.py'


def setup_app(tmp_path,monkeypatch,data=None):
    monkeypatch.setenv('VALUEPULSE_DB',str(tmp_path/'ui.sqlite3'))
    monkeypatch.setenv('FOOTBALL_DATA_API_KEY','')
    monkeypatch.setenv('ODDS_API_KEY','')
    calls=[]
    def fake_run(*args,**kwargs):
        calls.append(kwargs)
        return deepcopy(data or DashboardData('demo','Demo',[],generated_at=datetime.now(timezone.utc)))
    monkeypatch.setattr('valuepulse.pipeline.run',fake_run)
    return AppTest.from_file(str(APP), default_timeout=15).run(),calls


def test_navigation_and_calendar_do_not_fetch_again(tmp_path,monkeypatch):
    app,calls=setup_app(tmp_path,monkeypatch)
    assert not app.exception and len(calls)==1
    app.button(key='nav-calendar').click().run()
    assert not app.exception and len(calls)==1
    assert any('Gewählter Zeitraum' in item.value for item in app.markdown)
    next(button for button in app.button if button.key and button.key.startswith('day-')).click().run()
    assert not app.exception and len(calls)==1
    app.button(key='nav-analysis').click().run()
    assert not app.exception and len(calls)==1
    app.button(key='nav-positions').click().run()
    assert not app.exception and len(calls)==1
    assert any('Gesamter offener Einsatz'==metric.label for metric in app.metric)


def test_slip_rechecks_quotes_and_saves_separate_paper_position(tmp_path,monkeypatch):
    now=datetime.now(timezone.utc)
    matches=[_match(),_match('Liverpool','Everton')]
    for match in matches:
        match.kickoff=now+timedelta(days=1)
        match.books=tuple(replace(line,last_update=now) for line in match.books)
    app,calls=setup_app(tmp_path,monkeypatch,DashboardData('live','Live',matches,generated_at=now))
    assert not app.exception
    app.button(key='nav-strategy').click().run()
    assert not app.exception
    next(button for button in app.button if button.label=='Quoten prüfen & Tippschein generieren').click().run()
    assert not app.exception and len(calls)==2
    assert any('Anpfiff' in item.value and 'morgen' in item.value for item in app.markdown)
    next(button for button in app.button if button.label=='Schein im gewählten Positionsbuch speichern').click().run()
    assert not app.exception and not app.error
    app.button(key='nav-positions').click().run()
    assert not app.exception
    assert next(metric for metric in app.metric if metric.label=='Aktive Positionen').value=='1'
    app.selectbox(key='book_mode').select('real').run()
    assert not app.exception
    assert next(metric for metric in app.metric if metric.label=='Aktive Positionen').value=='0'
    app.selectbox(key='book_mode').select('paper').run()
    app.button(key='position-delete').click().run()
    assert not app.exception and not app.error
    assert next(metric for metric in app.metric if metric.label=='Aktive Positionen').value=='0'


def test_single_position_preserves_pick_and_provenance(tmp_path,monkeypatch):
    from contextlib import closing
    from valuepulse.db import connect
    from valuepulse.positions import list_positions
    now=datetime.now(timezone.utc)
    match=_match()
    match.kickoff=now+timedelta(days=1)
    match.books=tuple(replace(line,last_update=now) for line in match.books)
    app,calls=setup_app(tmp_path,monkeypatch,DashboardData('live','Live',[match],generated_at=now))
    button=next(button for button in app.button if button.label=='+ Tipp im gewählten Buch protokollieren')
    button.click().run()
    assert not app.exception and not app.error and len(calls)==2
    with closing(connect(tmp_path/'ui.sqlite3')) as conn:
        rows=list_positions(conn,'paper')
        assert len(rows)==1 and rows[0].bookmaker=='Book'
        assert rows[0].source=='the-odds-api' and rows[0].model_version
        assert rows[0].pick_label=='Heimsieg'


def test_analysis_and_quote_history_render_with_real_records(tmp_path,monkeypatch):
    from contextlib import closing
    from valuepulse.db import connect, save_quotes
    from valuepulse.history import record_predictions, forecasts, save_result
    from valuepulse.models import Quote
    now=datetime.now(timezone.utc)
    match=_match()
    match.kickoff=now-timedelta(days=1)
    stamp=now-timedelta(days=2)
    match.books=tuple(replace(line,last_update=stamp) for line in match.books)
    with closing(connect(tmp_path/'ui.sqlite3')) as conn:
        record_predictions(conn,[match],[],stamp)
        row=forecasts(conn)[0]
        save_result(conn,row['event_key'],2,0,now=now)
        save_quotes(conn,[Quote(match.competition,match.kickoff,match.home,match.away,'Book',1.8,4.,5.,stamp,'the-odds-api')],stamp)
    app,calls=setup_app(tmp_path,monkeypatch,DashboardData('live','Live',[match],generated_at=now))
    app.button(key='nav-analysis').click().run()
    assert not app.exception and not app.error
    assert next(metric for metric in app.metric if metric.label=='Ausgewertete Spiele').value=='1'
    assert len(app.dataframe)>=3
    app.button(key='nav-strategy').click().run()
    next(radio for radio in app.radio if 'Pro' in radio.options).set_value('Pro').run()
    assert not app.exception and not app.error
    assert any(expander.label=='Quotenverlauf' for expander in app.expander)


def test_failed_live_confirmation_never_creates_slip(tmp_path,monkeypatch):
    app,calls=setup_app(tmp_path,monkeypatch)
    app.button(key='nav-strategy').click().run()
    next(button for button in app.button if button.label=='Quoten prüfen & Tippschein generieren').click().run()
    assert not app.exception
    assert not app.session_state['slip_result'].legs
    assert not any(button.label=='Schein im gewählten Positionsbuch speichern' for button in app.button)

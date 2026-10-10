from datetime import timedelta
from contextlib import closing
import pytest

from tests.test_slip import NOW, _match
from valuepulse.db import connect, save_quotes
from valuepulse.history import record_predictions, forecasts, save_result, backtest, quote_history
from valuepulse.config import MODEL_VERSION
from valuepulse.models import Quote, Standing


def test_prospective_forecasts_are_immutable_and_deduplicated(tmp_path):
    with closing(connect(tmp_path/'db')) as conn:
        match=_match()
        table=[Standing('PL',name,10,20,15,12,updated_at=NOW) for name in ('Arsenal','Chelsea','Liverpool','Everton')]
        assert record_predictions(conn,[match],table,NOW)==1
        assert record_predictions(conn,[match],table,NOW+timedelta(minutes=1))==0
        rows=forecasts(conn)
        assert rows[0]['recorded_at']==NOW.isoformat()
        assert 'Arsenal' in rows[0]['inputs']
        table[0].goals_for=999
        assert '999' not in forecasts(conn)[0]['inputs']
        match.assessment.is_demo=True
        assert record_predictions(conn,[match],table,NOW)==0


def test_backtest_metrics_and_no_lookahead(tmp_path):
    with closing(connect(tmp_path/'db')) as conn:
        match=_match(p=.6,ev=.1)
        record_predictions(conn,[match],[],NOW)
        row=forecasts(conn)[0]
        with pytest.raises(ValueError): save_result(conn,row['event_key'],2,0,now=NOW)
        save_result(conn,row['event_key'],2,0,now=NOW+timedelta(days=2))
        rows=forecasts(conn)
        # A corrupted/imported future forecast must never enter retrospective metrics.
        leak=dict(rows[0],id=99,event_key='leak',recorded_at=(NOW+timedelta(days=2)).isoformat())
        result=backtest(rows+[leak],bookmaker='Book',model_version=MODEL_VERSION)
        assert result['n']==1 and result['bets']==1
        assert result['roi']==pytest.approx(1.1/.6-1)
        assert result['brier']==pytest.approx(.24)
        assert result['calibration'][0]['N']==1
        assert result['calibration'][0]['Beobachtet']==1
        save_result(conn,row['event_key'],0,2,now=NOW+timedelta(days=2))
        assert conn.execute('SELECT COUNT(*) FROM result_changes').fetchone()[0]==2
        assert backtest(forecasts(conn),bookmaker='Book',model_version=MODEL_VERSION)['roi']==-1


def test_one_forecast_per_event_and_filters(tmp_path):
    with closing(connect(tmp_path/'db')) as conn:
        first=_match(p=.6,ev=.1)
        record_predictions(conn,[first],[],NOW)
        second=_match(p=.7,ev=.08)
        record_predictions(conn,[second],[],NOW+timedelta(minutes=2))
        row=forecasts(conn)[0]
        save_result(conn,row['event_key'],1,0,now=NOW+timedelta(days=2))
        rows=forecasts(conn)
        initial=backtest(rows,bookmaker='Book',model_version=MODEL_VERSION,selection='first')
        latest=backtest(rows,bookmaker='Book',model_version=MODEL_VERSION,selection='last')
        assert initial['n']==latest['n']==1
        assert initial['details'][0]['p']==.6 and latest['details'][0]['p']==.7
        assert backtest(rows,bookmaker='Other',model_version=MODEL_VERSION)['n']==0
        assert backtest(rows,bookmaker='Book',model_version='other')['n']==0


def test_quote_history_and_duplicate_snapshot_timestamp(tmp_path):
    from valuepulse.db import latest_quotes
    with closing(connect(tmp_path/'db')) as conn:
        match=_match()
        quote=Quote(match.competition,match.kickoff,match.home,match.away,'Book',1.8,4.,5.,NOW,'the-odds-api')
        save_quotes(conn,[quote],NOW)
        quote.home_odds=1.9
        save_quotes(conn,[quote],NOW)
        assert len(latest_quotes(conn))==1 and latest_quotes(conn)[0].home_odds==1.9
        rows=quote_history(conn,match)
        assert [row['home_odds'] for row in rows]==[1.8,1.9]


def test_quote_history_matches_aliases_and_swapped_teams(tmp_path):
    with closing(connect(tmp_path/'db')) as conn:
        match=_match('FC Bayern München','Borussia Dortmund')
        match.competition='Bundesliga'
        quote=Quote('Bundesliga',match.kickoff,'Borussia Dortmund','Bayern Munich','Book',5.,4.,1.8,NOW,'the-odds-api')
        save_quotes(conn,[quote],NOW)
        rows=quote_history(conn,match)
        assert len(rows)==1 and rows[0]['home_odds']==1.8

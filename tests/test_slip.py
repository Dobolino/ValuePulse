from dataclasses import replace
from datetime import datetime, timedelta, timezone
import pytest

from valuepulse.models import Assessment, BookLine, MatchView
from valuepulse.slip import build_slip

NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)


def _match(home='Arsenal',away='Chelsea',*,p=.6,ev=.1,quality=90,book='Book',stamp=NOW,source='the-odds-api'):
    probabilities={'home':p,'draw':(1-p)/2,'away':(1-p)/2}
    prices={'home':(1+ev)/p,'draw':.92/((1-p)/2),'away':.92/((1-p)/2)}
    item=Assessment('home','Heimsieg',ev,probabilities,prices,{k:1/v for k,v in prices.items()},
        book,quality,[],'green','', '',used_table=True,book_odds={book:prices})
    return MatchView('Premier League',NOW+timedelta(days=1),'morgen',home,away,item,
        (BookLine(book,prices['home'],prices['draw'],prices['away'],stamp,source),))


def build(matches, count=3, risk='hoch', **kwargs):
    return build_slip(matches,count=count,risk=risk,now=NOW,**kwargs)


def test_kuerzung_team_integritaet_und_ev():
    slip=build([_match(ev=.12),_match('Arsenal','Fulham',ev=.11),_match('Liverpool','Everton',ev=.08)],count=3)
    assert len(slip.legs)==2 and slip.shortened
    assert 'Spielschein gekürzt!' in slip.warning
    assert slip.bookmaker=='Book'
    assert [(leg.home,leg.away) for leg in slip.legs]==[('Arsenal','Chelsea'),('Liverpool','Everton')]
    assert all(.03 < leg.edge <= .15 for leg in slip.legs)


def test_wenig_und_mittel_ranking():
    matches=[_match('A','B',p=.7,ev=.04),_match('C','D',p=.4,ev=.1),_match('E','F',p=.6,ev=.05)]
    assert [leg.home for leg in build(matches,risk='wenig').legs]==['A','E']
    assert [leg.home for leg in build(matches,risk='mittel').legs]==['C','E','A']
    assert [leg.home for leg in build(matches,risk='hoch').legs]==['C','E','A']


def test_kombi_und_kelly_cap():
    slip=build([_match(p=.7,ev=.05),_match('Liverpool','Everton',p=.6,ev=.1)],count=2,risk='wenig')
    assert slip.combined_odds==pytest.approx(1.5*(1.1/.6))
    assert slip.combined_probability==pytest.approx(.42)
    assert slip.stake==.01 and slip.stake_capped
    assert 'Unabhängigkeit' in slip.copy_text


def test_negative_ev_nach_buchmacherwechsel_ist_verboten():
    first=_match(p=.55,ev=.1); second=_match('Liverpool','Everton',p=.4,ev=.1)
    first.books=(BookLine('Bet365',1.8,3.4,4.2,NOW,'the-odds-api'),BookLine('Pinnacle',2.,3.3,4.,NOW,'the-odds-api'))
    second.books=(BookLine('Bet365',1.9,3.4,4.,NOW,'the-odds-api'),BookLine('Pinnacle',1.7,3.5,4.4,NOW,'the-odds-api'))
    slip=build([first,second],count=2)
    assert all(leg.probability*leg.odds-1 > .03 for leg in slip.legs)
    assert slip.bookmaker == "Pinnacle"
    assert any(leg.pick_label == "Unentschieden" for leg in slip.legs)


def test_spaetere_kandidaten_fuellen_gemeinsamen_buchmacher():
    matches=[_match('A','B',book='A',ev=.14),_match('C','D',book='B',ev=.12),_match('E','F',book='B',ev=.10)]
    slip=build(matches,count=2)
    assert slip.bookmaker=='B' and len(slip.legs)==2


def test_keine_gemischten_fallback_preise():
    matches=[_match(book='A'),_match('Liverpool','Everton',book='B')]
    for match in matches: match.books=()
    assert not build(matches).legs


@pytest.mark.parametrize('change', ['low_quality','demo','no_table','stale_table','started','unknown_stamp','old_quote','future_stamp','cache','excess_ev','longshot','nan'])
def test_unspielbare_kandidaten_gesperrt(change):
    match=_match()
    if change=='low_quality': match.assessment.quality=0
    if change=='demo': match.assessment.is_demo=True
    if change=='no_table': match.assessment.used_table=False
    if change=='stale_table': match.assessment.stale_table=True
    if change=='started': match.kickoff=NOW
    if change=='unknown_stamp': match.books=(replace(match.books[0],last_update=None),)
    if change=='old_quote': match.books=(replace(match.books[0],last_update=NOW-timedelta(minutes=16)),)
    if change=='future_stamp': match.books=(replace(match.books[0],last_update=NOW+timedelta(minutes=1)),)
    if change=='cache': match.books=(replace(match.books[0],source='cache'),)
    if change=='excess_ev': match=_match(ev=.3)
    if change=='longshot': match=_match(p=.1,ev=.1)
    if change=='nan': match.books=(replace(match.books[0],home=float('nan')),)
    assert not build([match],require_live=True).legs


def test_buchmacher_quote_hat_eigenes_alter():
    match=_match()
    match.books=(replace(match.books[0],bookmaker='old',last_update=NOW-timedelta(days=2)),replace(match.books[0],bookmaker='fresh'))
    assert build([match],require_live=True).bookmaker=='fresh'


def test_quote_100_und_anzahl_zwei_bis_zehn():
    matches=[_match(f'H{i}',f'A{i}',p=.9,ev=.1) for i in range(12)]
    assert len(build(matches,count=1).legs)==2
    assert len(build(matches,count=99).legs)==10
    long=[_match(f'H{i}',f'A{i}',p=.16,ev=.1) for i in range(10)]
    slip=build(long,count=10)
    assert slip.combined_odds <= 100 and all(leg.odds<=8 for leg in slip.legs)
    assert slip.shortened


def test_grenzen_ohne_anzeigerundung():
    assert not build([_match(ev=.03)]).legs
    assert build([_match(ev=.03001)]).legs
    assert build([_match(ev=.15)]).legs
    assert not build([_match(ev=.15001)]).legs

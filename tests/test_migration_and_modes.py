from contextlib import closing
import sqlite3
import pytest
from valuepulse.db import connect
from valuepulse.positions import add_position, list_positions, settle, summarize, exposure_by_team


def add(conn, mode='paper',**extra):
    return add_position(conn,sport='football',competition='PL',match_label='Arsenal – Chelsea',
        kickoff='2026-12-01T12:00:00+00:00',pick_label='Heimsieg',odds=2.,probability=.55,stake=2.,mode=mode,**extra)


def test_modes_do_not_mix_and_exposure_counts_combo_once(tmp_path):
    with closing(connect(tmp_path/'db')) as conn:
        paper=add(conn,legs=[{'home':'Arsenal','away':'Chelsea'},{'home':'Liverpool','away':'Everton'}])
        add(conn,mode='real')
        assert len(list_positions(conn,'paper'))==len(list_positions(conn,'real'))==1
        assert summarize(list_positions(conn,'paper')).open_stake==2
        assert len(exposure_by_team(list_positions(conn,'paper')))==4
        settle(conn,paper,'won')
        assert summarize(list_positions(conn,'paper')).pnl==2
        assert summarize(list_positions(conn,'real')).pnl==0
        assert conn.execute('SELECT COUNT(*) FROM position_changes').fetchone()[0]==1
        with pytest.raises(ValueError): add(conn,mode='real',source='demo')


def test_v1_database_migrates_without_losing_positions(tmp_path):
    path=tmp_path/'db'
    conn=sqlite3.connect(path)
    conn.executescript("""CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT INTO meta VALUES('schema_version','1');
        CREATE TABLE standings(competition TEXT,team TEXT,played INTEGER,points INTEGER,goals_for INTEGER,goals_against INTEGER,updated_at TEXT,PRIMARY KEY(competition,team));
        INSERT INTO standings VALUES('PL','Arsenal',10,20,15,8,'2026-10-10T12:00:00+00:00');
        CREATE TABLE positions(id INTEGER PRIMARY KEY,created_at TEXT,sport TEXT,competition TEXT,match_label TEXT,kickoff TEXT,pick_label TEXT,odds REAL,probability REAL,stake REAL,status TEXT,pnl REAL);
        INSERT INTO positions VALUES(7,'2026-10-01','football','PL','Arsenal – Chelsea','2026-10-12','Heimsieg',2,.55,4,'open',NULL);
        """)
    conn.close()
    with closing(connect(path)) as conn:
        rows=list_positions(conn,'legacy')
        assert len(rows)==1 and rows[0].id==7 and rows[0].stake==4
        assert not list_positions(conn,'real') and not list_positions(conn,'paper')
        assert conn.execute('SELECT COUNT(*) FROM standings').fetchone()[0]==1
        add(conn)
    with closing(connect(path)) as conn:
        assert len(list_positions(conn))==2
    assert not list(tmp_path.glob('*.bak'))

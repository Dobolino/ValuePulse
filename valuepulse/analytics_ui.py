"""Streamlit views for saved forecasts and genuine recorded quote snapshots."""
from contextlib import closing
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from valuepulse.config import load_settings
from valuepulse.db import connect
from valuepulse.history import forecasts, save_result, backtest, quote_history


def render_analysis() -> None:
    st.markdown('## Prognosen & Backtest')
    st.caption('Auswertung tatsächlich vor Anpfiff gespeicherter Prognosen. Keine nachträglich erfundenen historischen Vorhersagen.')
    with closing(connect(load_settings().db_path)) as conn:
        rows=forecasts(conn)
        if not rows:
            st.info('Noch keine Prognosen gespeichert. Ein Live-Abruf speichert Wahrscheinlichkeiten, Quoten, Modellversion und Eingangsdaten automatisch. Demo-Daten werden ausgeschlossen.')
            return
        st.metric('Gespeicherte Prognosen',len(rows))
        now=datetime.now(timezone.utc)
        events={row['event_key']:row for row in rows if datetime.fromisoformat(row['kickoff']) < now}
        with st.expander('Endergebnis erfassen oder korrigieren'):
            st.caption('Nur den bestätigten Endstand eintragen. Änderungen werden protokolliert. Diese Ergebnisse ändern das Positionsbuch nicht automatisch.')
            if events:
                key=st.selectbox('Spiel für Ergebnis',list(events),format_func=lambda k:f"{events[k]['home']} – {events[k]['away']} · {events[k]['kickoff'][:10]}")
                with st.form('result_form'):
                    a,b=st.columns(2)
                    home=a.number_input('Heimtore',0,50,int(events[key]['home_goals'] or 0))
                    away=b.number_input('Auswärtstore',0,50,int(events[key]['away_goals'] or 0))
                    if st.form_submit_button('Endergebnis speichern'):
                        save_result(conn,key,int(home),int(away))
                        st.rerun()
            else:
                st.info('Noch kein gespeichertes Spiel hat begonnen.')
        c1,c2=st.columns(2)
        book=c1.selectbox('Buchmacher für Auswertung',sorted({row['bookmaker'] for row in rows}))
        version=c2.selectbox('Modellversion',sorted({row['model_version'] for row in rows}))
        league=st.selectbox('Liga für Auswertung',['Alle']+sorted({row['competition'] for row in rows}))
        which=st.radio('Pro Spiel verwenden',['Erste Prognose','Letzte Prognose vor Anpfiff'],horizontal=True)
        result=backtest(rows,bookmaker=book,model_version=version,selection='first' if which=='Erste Prognose' else 'last',competition=None if league=='Alle' else league)
        a,b,c,d=st.columns(4)
        a.metric('Ausgewertete Spiele',result['n'])
        b.metric('Noch ohne Ergebnis',result['unsettled'])
        c.metric('Freigegebene Value-Tipps',result['bets'])
        d.metric('Simulierter ROI','—' if result['roi'] is None else f"{result['roi']:.1%}")
        st.caption('ROI: eine konstante Einheit je damals freigegebenem Tipp, ohne Gebühren; kein Kelly-Portfolio. Jede Partie zählt je Anbieter und Modellversion nur einmal. Kleine Stichproben sind nicht belastbar.')
        if result['n']:
            metrics=pd.DataFrame({'Modell':[result['brier'],result['log_loss']],
                'Markt desselben Anbieters':[result['market_brier'],result['market_log_loss']]},index=['Brier (0–2, kleiner besser)','Log Loss (kleiner besser)'])
            st.dataframe(metrics)
            st.caption('Markt-Baseline: proportional entfernte Marge desselben 1X2-Markts. Kein Vergleich mit nachträglichen Schlussquoten.')
            calibration=pd.DataFrame(result['calibration']).set_index('Band')
            st.markdown('**Kalibrierung der ausgewählten Ausgänge**')
            st.bar_chart(calibration[['Modell','Beobachtet']])
            st.dataframe(calibration)
            details=pd.DataFrame(result['details'])
            st.dataframe(details.drop(columns=['event_key']))
            st.download_button('Backtest als CSV',details.to_csv(index=False).encode('utf-8-sig'),'valuepulse-backtest.csv','text/csv')
        export=pd.DataFrame(rows).drop(columns=['inputs','fingerprint'],errors='ignore')
        st.download_button('Prognosehistorie als CSV',export.to_csv(index=False).encode('utf-8-sig'),'valuepulse-prognosen.csv','text/csv')
        with st.expander('Gespeicherte Eingangsdaten ansehen'):
            selected=st.selectbox('Prognose',rows,format_func=lambda row:f"#{row['id']} · {row['home']} – {row['away']} · {row['recorded_at']} · {row['bookmaker']}")
            st.json(selected)


def render_quote_history(match) -> None:
    with st.expander('Quotenverlauf'):
        with closing(connect(load_settings().db_path)) as conn:
            rows=quote_history(conn,match)
        if not rows:
            st.info('Noch keine echten Quotensnapshots für dieses Spiel gespeichert.')
            return
        frame=pd.DataFrame(rows)
        book=st.selectbox('Anbieter im Quotenverlauf',sorted(frame.bookmaker.unique()))
        chosen=frame[frame.bookmaker==book].copy()
        chosen['fetched_at']=pd.to_datetime(chosen['fetched_at'],utc=True)
        series=chosen.set_index('fetched_at')[['home_odds','draw_odds','away_odds']]
        st.line_chart(series.rename(columns={'home_odds':'Heim','draw_odds':'Remis','away_odds':'Auswärts'}))
        st.caption('Zeitachse: tatsächlicher Abruf. Angezeigt werden ausschließlich gespeicherte Preise; fehlende Zeiträume werden nicht mit erfundenen Quoten ergänzt.')
        st.dataframe(chosen)
        st.download_button('Quoten als CSV',chosen.to_csv(index=False).encode('utf-8-sig'),'valuepulse-quoten.csv','text/csv')

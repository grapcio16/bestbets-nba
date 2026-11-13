"""Synthetic offline fixtures only; no fixture scores are shipped to the app."""
import copy
import os
import unittest
from unittest.mock import patch
import pandas as pd
from bestbets_free_analyses import (extract_free_leaders, get_free_leader_boxscore,
    detail_key, select_leader, photo_policy, integer)

NOW = pd.Timestamp('2026-11-13T12:00:00Z')

def event(eid='401234567', date='2026-11-12T23:00:00Z'):
    teams=[]
    for i, (code, side) in enumerate((('BOS','home'),('NYK','away'))):
        groups=[]
        for j, (name, value) in enumerate((('points',26),('rebounds',10),('assists',8))):
            groups.append({'name':name,'leaders':[{'value':value-i,
                'athlete':{'id':str(10+j+3*i),'displayName':['Test Scorer','Test Rebounder','Test Passer'][j]+(' Away' if i else '')}}]})
        teams.append({'homeAway':side,'team':{'abbreviation':code},'leaders':groups})
    return {'id':eid,'date':date,'status':{'type':{'completed':True,'state':'post'}},
            'competitions':[{'id':eid,'date':date,'status':{'type':{'completed':True,'state':'post'}},'competitors':teams}]}

def summary(leader):
    e=event(leader['game_id'],leader['event_date'])
    return {'header':{'id':e['id'],'competitions':e['competitions']},
        'boxscore':{'players':[{'team':{'abbreviation':leader['team']},'statistics':[
            {'labels':['MIN','PTS','REB','AST','3PT'],'athletes':[{
                'athlete':{'id':leader['athlete_id'],'displayName':leader['name']},
                'stats':['32','26','7','5','3-7']}]}]}]}}

def free_fixture(rows):
    """Add the server's new schema to older LOCAL browser fixtures."""
    result=[]
    for i, row in enumerate(rows):
        row={**row,'athlete_id':row.get('athlete_id',str(10+i)),
             'game_id':row.get('game_id',str(401234567+i)),
             'opponent':row.get('opponent','NYK'),'home_away':'home'}
        row['detail_key']=detail_key(row);result.append(row)
    return {'free_leaders':result,'free_leader_day':result[0]['date'] if result else '',
            'free_schema':1,'free_photos_enabled':False}

class FreeAnalysesTest(unittest.TestCase):
    def rows(self, raw=None):
        return extract_free_leaders(raw or {'events':[event()]}, NOW)

    def leader(self):
        return self.rows()['free_leaders'][0]

    def test_independent_categories_and_same_player_can_win_all(self):
        e=event(); groups=e['competitions'][0]['competitors'][0]['leaders']
        for group in groups: group['leaders'][0]['athlete']={'id':'10','displayName':'Test Leader'}
        rows=self.rows({'events':[e]})['free_leaders']
        self.assertEqual([r['market'] for r in rows],['PTS','REB','AST'])
        self.assertEqual([r['athlete_id'] for r in rows],['10']*3)
        self.assertEqual(len({r['detail_key'] for r in rows}),3)

    def test_maximum_across_all_games_not_three_highest_scorers(self):
        e=event('401234568');e['competitions'][0]['competitors'][1]['leaders'][1]['leaders'][0]['value']=24
        rows=self.rows({'events':[event(),e]})['free_leaders']
        self.assertEqual(rows[1]['value'],24)
        self.assertEqual(rows[1]['team'],'NYK')
        self.assertEqual(rows[0]['value'],26)

    def test_latest_day_precedes_stat_filtering_no_old_day_backfill(self):
        latest=event('401234568');latest['competitions'][0]['competitors'][0]['leaders']=[]
        out=self.rows({'events':[event(date='2026-11-11T23:00Z'),latest]})
        self.assertEqual(out['free_leader_day'],'2026-11-12')
        self.assertEqual(out['free_leaders'],[])
        self.assertEqual(out['free_missing_categories'],['PTS','REB','AST'])

    def test_one_missing_team_category_is_honest(self):
        e=event();e['competitions'][0]['competitors'][1]['leaders'].pop()
        out=self.rows({'events':[e]})
        self.assertEqual([r['market'] for r in out['free_leaders']],['PTS','REB'])
        self.assertEqual(out['free_missing_categories'],['AST'])

    def test_et_slate_not_split_at_warsaw_midnight(self):
        a=event(date='2026-11-12T22:00Z');b=event('401234568','2026-11-13T03:30Z')
        b['competitions'][0]['competitors'][0]['leaders'][0]['leaders'][0]['value']=40
        out=self.rows({'events':[a,b]})
        self.assertEqual(out['free_leader_day'],'2026-11-12')
        self.assertEqual(out['free_leaders'][0]['value'],40)
        self.assertEqual(out['free_leaders'][0]['local_date'],'2026-11-13')

    def test_live_future_false_string_and_conflicting_status_ignored(self):
        for status in ({'completed':False},{'completed':'true'},{'completed':True,'state':'in'}):
            e=event();e['status']['type']=status;e['competitions'][0]['status']['type']=status
            self.assertEqual(self.rows({'events':[e]})['free_leaders'],[])
        self.assertEqual(self.rows({'events':[event(date='2026-11-14T23:00Z')]})['free_leaders'],[])

    def test_missing_newer_source_day_does_not_claim_older_leaders(self):
        out=extract_free_leaders({'events':[event()]},NOW,covered_days=['20261112'])
        self.assertEqual(out['free_leaders'],[])
        self.assertIn('Niepełne',out['free_warning'])

    def test_numeric_validation_never_rounds_or_accepts_bool(self):
        for value in (True,False,'39.99',-1,float('nan'),float('inf'),'1000'):
            self.assertIsNone(integer(value,100))
        self.assertEqual(integer('39',100),39)

    def test_bad_id_cannot_load_photo_or_details(self):
        for value in ('../10','10/x','1'*21,''):
            e=event();e['competitions'][0]['competitors'][0]['leaders'][0]['leaders'][0]['athlete']['id']=value
            self.assertEqual(self.rows({'events':[e]})['free_missing_categories'],['PTS'])

    def test_normalize_team_aliases(self):
        for source,target in (('UTAH','UTA'),('PHO','PHX'),('GS','GSW'),('WSH','WAS')):
            e=event();e['competitions'][0]['competitors'][0]['team']['abbreviation']=source
            self.assertEqual(self.rows({'events':[e]})['free_leaders'][0]['team'],target)

    def test_equal_maximum_is_stable_and_marked(self):
        e=event('401234568');e['competitions'][0]['competitors'][0]['leaders'][0]['leaders'][0]['athlete']['id']='99'
        a=self.rows({'events':[event(),e]})['free_leaders'][0]
        b=self.rows({'events':[e,event()]})['free_leaders'][0]
        self.assertEqual(a,b);self.assertEqual(a['tie_count'],2)

    def test_only_server_snapshot_key_is_accepted(self):
        leader=self.leader(); snap={'free_leaders':[leader]}
        self.assertEqual(select_leader(snap,leader['detail_key']),leader)
        for key in (None,0,'../10','a'*64,{'athlete_id':'10'}):self.assertIsNone(select_leader(snap,key))
        self.assertIsNone(select_leader({'free_leaders':[{**leader,'value':50}]},leader['detail_key']))

    def test_photos_explicitly_opt_in(self):
        for env,expected in (({},False),({'BESTBETS_CENTRE_HEADSHOTS_LICENSED':'false'},False),({'BESTBETS_CENTRE_HEADSHOTS_LICENSED':'true'},True)):
            with patch.dict(os.environ,env,clear=True):self.assertEqual(photo_policy(),expected)

    def test_verified_single_game_boxscore(self):
        leader=self.leader()
        with patch('sources.memoized_json',return_value=(summary(leader),{'stale':False})) as fetch:
            out=get_free_leader_boxscore(leader)
        self.assertEqual([out[k] for k in ('PTS','REB','AST','3PM')],[26,7,5,3])
        self.assertTrue(out['verified']);self.assertEqual(fetch.call_args.kwargs['params'],{'event':'401234567'})
        self.assertEqual(fetch.call_args.kwargs['ttl_seconds'],120)

    def test_inconsistent_header_identity_stats_fail_closed(self):
        leader=self.leader();good=summary(leader)
        bad=[]
        p=copy.deepcopy(good);p['header']['id']='99';bad.append(p)
        p=copy.deepcopy(good);p['header']['competitions'][0]['status']['type']['completed']=False;bad.append(p)
        p=copy.deepcopy(good);p['header']['competitions'][0]['date']='2026-11-11T23:00Z';bad.append(p)
        p=copy.deepcopy(good);p['header']['competitions'][0]['competitors'][0]['team']['abbreviation']='LAL';bad.append(p)
        for field,value in (('id','999'),('displayName','Wrong Person')):
            p=copy.deepcopy(good);p['boxscore']['players'][0]['statistics'][0]['athletes'][0]['athlete'][field]=value;bad.append(p)
        for stats in (['32','25','7','5','3-7'],['32','26','7','5','--'],['32','26','7.01','5','3-7']):
            p=copy.deepcopy(good);p['boxscore']['players'][0]['statistics'][0]['athletes'][0]['stats']=stats;bad.append(p)
        for payload in bad:
            with self.subTest(payload=payload),patch('sources.memoized_json',return_value=(payload,{})):
                with self.assertRaises(ValueError):get_free_leader_boxscore(leader)

    def test_outage_never_returns_sample_stats(self):
        with patch('sources.memoized_json',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):get_free_leader_boxscore(self.leader())

    def test_server_event_ignores_client_ids_and_does_not_run_props(self):
        import bestbets_custom_screen as app
        leader=self.leader();snapshot={'games':[],'ticker':[],**self.rows()}
        for forged in (False,True):
            key='0'*64 if forged else leader['detail_key']
            session={'bb10_centre_data':snapshot}
            with patch.object(app.st,'session_state',session),patch.object(app.st,'markdown'),patch.object(app.st,'rerun'),patch.object(app,'_cached_brand',return_value=''),patch.object(app,'_research') as research,patch.object(app,'_cached_free_details',return_value={'verified':True}) as fetch,patch.object(app,'COMPONENT',return_value={'id':'test','type':'free_leader_details','key':key,'athlete_id':'999','url':'https://invalid.test'}):
                app.main()
            research.assert_not_called()
            if forged:fetch.assert_not_called();self.assertTrue(session['bb10_free_leader_details']['error'])
            else:fetch.assert_called_once_with(leader)

if __name__=='__main__':unittest.main()

import unittest
from datetime import datetime,timezone,timedelta
from pipeline.weekly_roles import assign_roles,depth_slots
NOW=datetime(2026,11,12,tzinfo=timezone.utc)
def player(pid,pos='QB',unavailable=False):
 return dict(player_id=str(pid),team_id='2',position=pos,unavailable=unavailable,availability='Out' if unavailable else 'Active')
def chart(ids):return {'2':{'depthchart':[{'positions':{'qb':{'athletes':[{'id':str(i)} for i in ids]}}}]}}
class RoleTests(unittest.TestCase):
 def test_only_one_healthy_qb_starter(self):
  rows=assign_roles([player(1),player(2)],chart([1,2]),[],NOW)
  self.assertTrue(rows[0]['role_eligible']);self.assertFalse(rows[1]['role_eligible'])
 def test_out_starter_promotes_verified_backup_without_transferring_stats(self):
  rows=assign_roles([player(1,unavailable=True),player(2)],chart([1,2]),[],NOW)
  self.assertFalse(rows[0]['role_eligible']);self.assertEqual(rows[1]['role'],'Injury replacement candidate');self.assertNotIn('stats',rows[1])
 def test_questionable_does_not_promote_backup(self):
  starter=player(1);starter['availability']='Questionable'
  rows=assign_roles([starter,player(2)],chart([1,2]),[],NOW)
  self.assertTrue(rows[0]['role_eligible']);self.assertFalse(rows[1]['role_eligible'])
 def test_missing_depth_never_guesses_qb_starter(self):
  self.assertFalse(assign_roles([player(1)],{},[],NOW)[0]['role_eligible'])
 def test_regular_receiver_requires_repeated_meaningful_recent_usage(self):
  def summary(days,targets):
   return {'_weekly_completed':True,'_weekly_event_date':(NOW-timedelta(days=days)).isoformat(),'boxscore':{'players':[{'team':{'id':'2'},'statistics':[{'name':'receiving','keys':['receivingTargets'],'athletes':[{'athlete':{'id':'3'},'stats':[str(targets)]}]}]}]}}
  self.assertTrue(assign_roles([player(3,'WR')],{},[summary(4,5),summary(11,4)],NOW)[0]['role_eligible'])
  self.assertFalse(assign_roles([player(3,'WR')],{},[summary(4,1),summary(11,1)],NOW)[0]['role_eligible'])
  self.assertFalse(assign_roles([player(3,'WR')],{},[summary(20,5),summary(27,4)],NOW)[0]['role_eligible'])
 def test_returner_is_not_offensive_starter(self):
  payload={'depthchart':[{'positions':{'pr':{'athletes':[{'id':'3'}]}}}]}
  self.assertEqual(depth_slots(payload),[])

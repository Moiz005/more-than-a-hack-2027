"""L1-L12 acceptance contracts; no real-match labels or metrics."""
import unittest
from starter_v6.tests.lifecycle_harness import *


class LifecycleCatalogTests(unittest.TestCase):
    def exact(self,samples,events,labels,spells):
        result=lifecycle(samples,events)
        self.assertEqual(result['labels'],labels)
        self.assertEqual(result['spells'],spells)
        report=spell_report(spells,result['spells'])
        self.assertEqual(report['matched'],len(spells))
        self.assertEqual(report['false_splits']+report['missed_splits'],0)
        self.assertTrue(all(p['iou']==1 and p['start_offset']==p['end_offset']==0 for p in report['pairs']))
        return result

    def test_L1_same_team_stop(self):
        self.exact(live()+setup()+delivery(),[event(4,11)],'HHHHDDDHHHH',[('H',0,3),('H',7,10)])

    def test_L2_stop_then_away(self):
        self.exact(live()+setup()+delivery('A'),[event(4,11)],'HHHHDDDAAAA',[('H',0,3),('A',7,10)])

    def test_L3_direct_takeover(self):
        self.exact(live()+live(owner='A'),[],'HHHHAAAA',[('H',0,3),('A',4,7)])

    def test_L4_deflection_is_ambiguous_not_control(self):
        # A missing observation encodes unresolved contact, not a known A owner.
        self.exact(live()+gap(2)+live(),[],'H'*10,[('H',0,9)])
        self.exact(live()+live(1,owner='A')+live(),[],'H'*9,[('H',0,8)])

    def test_L5_comprehensive_boundary_gap_throwin_new_stop(self):
        # Reappearance starts .9 m from the last visible boundary coordinate,
        # within the existing runtime detector's 1 m displacement gate.
        s=live(x=.1)+[Sample(-1.1,30.,None)]+gap(3)+delivery(x=-.5)
        s+=live(2,x=.7,speed=.1)+[Sample(-.2,22.5,'H'),Sample(-1.2,25.,None)]
        r=self.exact(s,[event(4,len(s),'Throw-in')],'H'*4+'D'*4+'H'*7+'D',
                     [('H',0,3),('H',8,14)])
        self.assertTrue(r['rows'][4]['evidence']['confirmed'])
        self.assertIn('confirmed_stoppage_memory',r['rows'][5]['evidence']['source'])
        self.assertEqual(r['rows'][8]['restart_action'],'restart_reappearance')
        self.assertTrue(r['rows'][12]['consumed'])
        self.assertEqual(r['rows'][-1]['evidence']['cues'],('out_of_bounds',))

    def test_L6_supported_restarts_and_unsupported_penalty(self):
        for kind in ('Free Kick','Corner Kick','Goal Kick','Kick off (start)','Kick off (after goal)'):
            with self.subTest(kind=kind):
                self.exact(setup()+delivery(),[event(0,7,kind),event(0,3,code='GOALS')],
                           'DDDHHHH',[('H',3,6)])
        # Penalty is not a recognized restart type: tag alone cannot establish D.
        self.exact(setup()+delivery(),[event(0,7,'Penalty')],'H'*7,[('H',0,6)])

    def test_L7_goalkeeper_and_slow_live(self):
        for speed in (0.,.1,.3,1.):
            self.exact(live(6,speed=speed),[],'H'*6,[('H',0,5)])

    def test_L8_consumed_context_and_independent_boundary(self):
        from starter_v6.tests.test_v3_phase0_characterization import overlong_tag_trace
        self.assertEqual(overlong_tag_trace()[2],'DDDHHHHHH')
        # L8B's independent second stoppage is exercised by comprehensive L5.

    def test_L9_live_missing_retained_and_expired(self):
        self.exact(live()+gap(4)+live(),[],'H'*12,[('H',0,11)])
        r=lifecycle(setup()+gap(30)+delivery(),[event(0,37)])
        d=[x['emission']['dead'] for x in r['rows']]
        self.assertGreater(d[3],d[27])
        self.assertAlmostEqual(d[28],1/3)
        self.assertTrue(all(not x['evidence']['confirmed'] for x in r['rows'][3:33]))
        self.assertEqual(d[33],0.)
        self.assertEqual(r['labels'][:28],'D'*28)
        # Neutral frames can remain D; record the actual path without forcing it.

    def test_L10_quality_halves_ungraded_and_pre_kickoff(self):
        r=lifecycle(live(1,x=80.)+[Sample(-1.1,30.,None),Sample(-1.1,0.,None)])
        self.assertFalse(r['rows'][1]['evidence']['confirmed'])
        self.assertTrue(r['rows'][2]['evidence']['confirmed'])
        self.assertAlmostEqual(r['rows'][1]['emission']['dead'],1/3)
        s=setup()+[Sample(None,None,None,0)]+setup(half=2)+delivery(half=2)
        r=self.exact(s,[event(0,len(s),'Kick off (start)')],'DDDXDDDHHHH',[('H',7,10)])
        self.assertFalse(r['rows'][4]['consumed'])
        self.assertEqual([x['frame'] for x in r['rows']],list(range(len(s))))
        r=lifecycle([Sample(.1,1.,'H'),Sample(-1.1,1.,None)])
        self.assertTrue(r['rows'][1]['quality']['ball_speed_inconsistent'])
        self.assertFalse(r['rows'][1]['quality']['implausible_ball_jump'])
        self.assertTrue(r['rows'][1]['evidence']['confirmed'])

    def test_L11_short_structural_stop_vs_outlier(self):
        self.exact(live(4,x=.1)+[Sample(-1.1,30.,None)]+live(4,x=.1),[],
                   'HHHHDHHHH',[('H',0,3),('H',5,8)])
        self.exact(live(4,x=80.)+[Sample(-1.1,30.,None)]+live(4,x=80.),[],
                   'H'*9,[('H',0,8)])

    def test_L12_restart_without_confirmed_dead(self):
        r=lifecycle(setup(1)+delivery(),[event(0,5)])
        self.assertFalse(r['rows'][0]['evidence']['confirmed'])
        self.assertEqual(r['rows'][1]['restart_action'],'restart_delivery')
        self.assertEqual(r['rows'][1]['evidence']['live_score'],.9)
        self.assertEqual(r['labels'],'H'*5)

    def test_spell_matching_detects_splits_merges_and_offsets(self):
        expected=[('H',0,3),('H',6,9)]
        merged=spell_report(expected,[('H',0,9)])
        self.assertEqual(merged['merged_neighbors'],1)
        self.assertEqual(merged['matched'],0) # each IoU .4, below prespecified .5
        split=spell_report([('H',0,9)],expected)
        self.assertEqual(split['false_splits'],1)
        offset=spell_report([('A',0,4)],[('A',1,5)])
        self.assertEqual(offset['pairs'][0]['start_offset'],1)

    def test_neutral_expiry_does_not_force_decoder_live(self):
        r=lifecycle(setup()+gap(30),[event(0,33)])
        self.assertAlmostEqual(r['rows'][28]['emission']['dead'],1/3)
        self.assertEqual(r['rows'][28]['evidence']['validity'],('ball_missing','expired'))
        self.assertEqual(r['labels'],'D'*33)

    def test_spell_matcher_agrees_with_official_synthetic_matching(self):
        from evaluation.possession_metrics import spell_overlaps,match_spells
        expected=[('H',0,3),('H',6,9),('A',10,14)]
        actual=[('H',0,9),('A',11,15)]
        convert=lambda ss:[(a,b+1,0 if t=='H' else 1) for t,a,b in ss]
        overlaps=spell_overlaps(convert(expected),convert(actual))
        tp,fp,fn=match_spells(overlaps,len(expected),len(actual),.5)
        ours=spell_report(expected,actual)
        self.assertEqual((ours['matched'],ours['unmatched_actual'],ours['unmatched_expected']),(tp,fp,fn))

    def test_noisy_context_with_moving_ball_and_invalid_players(self):
        self.exact(live(6),[event(0,6)],'H'*6,[('H',0,5)])
        r=lifecycle([Sample(10.,1.,None)]*4)
        self.assertTrue(all(x['quality']['low_player_coverage'] for x in r['rows']))
        self.assertTrue(all(not x['evidence']['confirmed'] for x in r['rows']))

"""Invented context lifecycle tests using production adapter and inference."""
from dataclasses import replace
import unittest
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from starter_v6.tests.test_v3_phase0_characterization import overlong_tag_trace
from starter_v6.pipeline import RuntimeRestartActionDetector, restart_frame_mask
from starter_v6.possession import FrameEvidence, PlayerEvidence
from starter_v6.inference import iter_infer_e02
from starter_v6.hmm import decode, HMMConfig
from starter_v6.synthetic import tag_event


def trace(motion, mask=None, halves=None, players=()):
    detector = RuntimeRestartActionDetector()
    fs = [detector.observe(FrameEvidence(i, halves[i] if halves else 1,
          None if x is None else (x,10.), players, s, bool(mask[i]) if mask is not None else True))
          for i,(x,s) in enumerate(motion)]
    rs = list(iter_infer_e02(fs))
    labels = ['X']*len(rs)
    for half in (1,2):
        ids=[i for i,r in enumerate(rs) if r.emission.half==half]
        ls,_=decode([rs[i].emission for i in ids],config=HMMConfig())
        for i,l in zip(ids,ls): labels[i]=l
    return fs,rs,''.join(labels)


SETUP=[(10.,.1)]*3
DELIVERY=[(10.3,2.),(10.6,2.)]


class ContextConsumptionTests(unittest.TestCase):
    def test_causal_comparison_to_protected_phase0_tree(self):
        script = '''
import json
from dataclasses import asdict
from starter_v6.pipeline import RuntimeRestartActionDetector
from starter_v6.possession import FrameEvidence
from starter_v6.inference import iter_infer_e02
from starter_v6.hmm import decode,HMMConfig
out=[]
for motion in ([(10.,.1)]*3+[(10.3,2.),(10.6,2.)]+[(10.6,.1)]*4,
               [(10.,.1)]*3+[(10.3,2.),(10.6,2.)]+[(-1.,.1)]*2):
 d=RuntimeRestartActionDetector()
 fs=[d.observe(FrameEvidence(i,1,(x,10.),(),s,True)) for i,(x,s) in enumerate(motion)]
 rs=list(iter_infer_e02(fs))
 out.append({'labels': ''.join(decode([r.emission for r in rs],config=HMMConfig())[0]),
 'cues':[r.inference.dead_ball_evidence.cues for r in rs],
 'confirmed':[r.inference.dead_ball_evidence.confirmed for r in rs],
 'emissions':[[r.emission.home,r.emission.away,r.emission.dead] for r in rs],
 'team':[asdict(r.inference.team_evidence) for r in rs]})
print(json.dumps(out))
'''
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix='v3-phase0-oracle-') as folder:
            archive=subprocess.run(['git','archive','e04-v3-phase0-persistence-baseline'],
                                   cwd=root,capture_output=True,check=True)
            subprocess.run(['tar','-x','-C',folder],input=archive.stdout,check=True)
            baseline=json.loads(subprocess.check_output([sys.executable,'-B','-c',script],cwd=folder))
        current=json.loads(subprocess.check_output([sys.executable,'-B','-c',script],cwd=root))
        self.assertEqual(baseline[0]['labels'],'DDDHHDDDD')
        self.assertEqual(current[0]['labels'],'DDDHHHHHH')
        self.assertEqual(baseline[0]['cues'][6],['restart_stationary'])
        self.assertEqual(current[0]['cues'][6],[])
        self.assertTrue(baseline[0]['confirmed'][6])
        self.assertFalse(current[0]['confirmed'][6])
        self.assertEqual(baseline[0]['emissions'][6],[.0050000000000000044,.0050000000000000044,.99])
        self.assertEqual(current[0]['emissions'][6],[.5,.5,0.])
        self.assertEqual(baseline[0]['team'],current[0]['team'])
        self.assertEqual(baseline[1],current[1])

    def test_independent_boundary_after_consumption(self):
        fs,rs,labels=trace(SETUP+DELIVERY+[(10.6,.1)]*2+[(-1.,.1)]*2)
        self.assertEqual(labels,'DDDHHHHDD')
        self.assertTrue(fs[-1].restart_context_consumed)
        self.assertEqual(rs[-1].inference.dead_ball_evidence.cues,('out_of_bounds',))
        self.assertTrue(rs[-1].inference.dead_ball_evidence.confirmed)

    def test_gap_rearms_same_kind_context_and_second_delivery(self):
        fs,rs,labels=trace(SETUP+DELIVERY+[(10.6,2.)]+SETUP+DELIVERY,
                          mask=[1]*5+[0]+[1]*5)
        self.assertEqual(labels,'DDDHHHDDDHH')
        self.assertFalse(fs[6].restart_context_consumed)
        self.assertEqual(fs[9].restart_action,'restart_delivery')

    def test_overlapping_contiguous_and_merged_masks_are_conservative(self):
        for intervals in (((0,7),(3,9)),((0,5),(5,9)),((0,9),)):
            mask=restart_frame_mask([tag_event('SET PIECES',a,b,tag_type='Free Kick')
                                     for a,b in intervals],9)
            fs,rs,labels=trace(SETUP+DELIVERY+[(10.6,.1)]*4,mask)
            self.assertEqual(labels,'DDDHHHHHH')
            self.assertTrue(all(f.restart_context_consumed for f in fs[3:]))

    def test_no_delivery_or_unreliable_jump_does_not_consume(self):
        for motion in (SETUP*2,SETUP+[(80.,None),(None,None)]):
            fs,rs,_=trace(motion)
            self.assertFalse(any(f.restart_context_consumed for f in fs))
            self.assertTrue(rs[2].inference.dead_ball_evidence.confirmed)

    def test_halves_rearm_even_if_mask_remains_active(self):
        fs,rs,labels=trace(SETUP+DELIVERY+SETUP+DELIVERY,halves=[1]*5+[2]*5)
        self.assertEqual(labels,'DDDHHDDDHH')
        self.assertFalse(fs[5].restart_context_consumed)
        self.assertTrue(rs[6].inference.dead_ball_evidence.confirmed)

    def test_missing_after_delivery_does_not_reactivate_retired_memory(self):
        fs,rs,labels=trace(SETUP+DELIVERY+[(None,None)]*4+[(10.6,.1)]*3)
        self.assertTrue(all(f.restart_context_consumed for f in fs[3:]))
        self.assertTrue(all(r.emission.dead==0 for r in rs[3:]))

    def test_independent_collective_motion_cue_is_not_suppressed(self):
        players=tuple(PlayerEvidence('H' if i%2 else 'A',30.+i,20.,0.) for i in range(8))
        fs,rs,_=trace(SETUP+DELIVERY+[(10.6,.1)]*3,players=players)
        self.assertEqual(rs[-1].inference.dead_ball_evidence.cues,('stationary_context',))
        self.assertTrue(rs[-1].inference.dead_ball_evidence.confirmed)

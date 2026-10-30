"""Invented production-path boundary-quality counterfactuals."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig
from starter_v6.inference import iter_infer_e02
from starter_v6.hmm import decode,HMMConfig


def run(xs, speeds=None, players=()):
    fs=[FrameEvidence(i,1,None if x is None else (x,10.),players,
                      speeds[i] if speeds else 30.) for i,x in enumerate(xs)]
    rs=list(iter_infer_e02(fs))
    return rs,''.join(decode([r.emission for r in rs],config=HMMConfig())[0])


class BoundaryQualityTests(unittest.TestCase):
    def test_reliable_crossing_and_speed_mismatch_only_remain_hard(self):
        for speed in (30.,1.):
            rs,labels=run([.1,-1.1,.1],[speed]*3)
            self.assertFalse(rs[1].features.quality.implausible_ball_jump)
            self.assertTrue(rs[1].inference.dead_ball_evidence.hard_evidence)
            self.assertEqual(rs[1].emission.dead,1.)
            self.assertEqual(labels,'HDH')

    def test_isolated_jump_is_uncertain_not_hard_and_cannot_seed_memory(self):
        rs,labels=run([80.,-1.1,80.,None,None])
        r=rs[1]
        self.assertTrue(r.features.quality.implausible_ball_jump)
        self.assertFalse(r.inference.dead_ball_evidence.hard_evidence)
        self.assertFalse(r.inference.dead_ball_evidence.confirmed)
        self.assertAlmostEqual(r.emission.dead,1/3)
        self.assertEqual(labels,'HHHHH')
        self.assertTrue(all('confirmed_stoppage_memory' not in x.inference.dead_ball_evidence.source for x in rs))

    def test_later_consistent_boundary_recovers_and_seeds_memory(self):
        rs,labels=run([80.,-1.1,-1.1,None],[30.,30.,0.,None])
        self.assertFalse(rs[1].inference.dead_ball_evidence.confirmed)
        self.assertFalse(rs[2].features.quality.implausible_ball_jump)
        self.assertTrue(rs[2].inference.dead_ball_evidence.confirmed)
        self.assertEqual(rs[2].emission.dead,1.)
        self.assertIn('confirmed_stoppage_memory',rs[3].inference.dead_ball_evidence.source)

    def test_invalid_boundary_does_not_seed_disappearance_history(self):
        rs,_=run([80.,-1.1]+[None]*55)
        self.assertTrue(all(not r.inference.dead_ball_evidence.cues for r in rs[2:]))

    def test_in_play_jump_and_uncorroborated_missing_stay_non_dead(self):
        for xs in ([10.,80.,10.],[10.,None,None,10.]):
            rs,labels=run(xs)
            self.assertNotIn('D',labels)
            self.assertTrue(all(r.emission.dead==0 for r in rs))

    def test_independent_collective_cue_survives_suspicious_boundary(self):
        players=tuple(PlayerEvidence('H' if i%2 else 'A',30.+i,20.,0.) for i in range(8))
        rs,_=run([80.,-1.1,-80.],[0.]*3,players)
        self.assertTrue(rs[-1].features.quality.implausible_ball_jump)
        self.assertEqual(rs[-1].inference.dead_ball_evidence.cues,('stationary_context',))
        self.assertTrue(rs[-1].inference.dead_ball_evidence.confirmed)

    def test_half_reset_no_cross_half_jump(self):
        fs=[FrameEvidence(0,1,(80.,10.),(),30.),FrameEvidence(1,2,(-1.1,10.),(),0.)]
        rs=list(iter_infer_e02(fs))
        self.assertFalse(rs[1].features.quality.implausible_ball_jump)
        self.assertTrue(rs[1].inference.dead_ball_evidence.confirmed)

    def test_protected_phase1_causal_oracle(self):
        script='''
import json
from starter_v6.possession import FrameEvidence
from starter_v6.inference import iter_infer_e02
from starter_v6.hmm import decode,HMMConfig
out=[]
for xs,ss in [([.1,-1.1,.1],[30.]*3),([80.,-1.1,80.],[30.]*3),([80.,-1.1,-1.1,None],[30.,30.,0.,None])]:
 rs=list(iter_infer_e02([FrameEvidence(i,1,None if x is None else (x,10.),(),ss[i]) for i,x in enumerate(xs)]))
 out.append({'labels':''.join(decode([r.emission for r in rs],config=HMMConfig())[0]),'D':[r.emission.dead for r in rs], 'confirmed':[r.inference.dead_ball_evidence.confirmed for r in rs]})
print(json.dumps(out))
'''
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix='boundary-phase1-oracle-') as folder:
            archive=subprocess.run(['git','archive','bd757b493180a96b39d2c57e5901829d4d507b87'],cwd=root,capture_output=True,check=True)
            subprocess.run(['tar','-x','-C',folder],input=archive.stdout,check=True)
            old=json.loads(subprocess.check_output([sys.executable,'-B','-c',script],cwd=folder))
        new=json.loads(subprocess.check_output([sys.executable,'-B','-c',script],cwd=root))
        self.assertEqual(old[0],new[0])
        self.assertEqual(old[1]['labels'],'HDH')
        self.assertEqual(new[1]['labels'],'HHH')
        self.assertEqual(old[1]['D'][1],1.)
        self.assertAlmostEqual(new[1]['D'][1],1/3)
        self.assertFalse(new[2]['confirmed'][1])
        self.assertTrue(new[2]['confirmed'][2])

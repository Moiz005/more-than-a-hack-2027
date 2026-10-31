"""Frozen-source synthetic comparisons; never read competition assets or truth."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from starter_v6.inference import iter_infer_e02
from starter_v6.hmm import decode,HMMConfig
from starter_v6.possession import PossessionConfig
from starter_v6.tests.test_dead_ball_persistence import run
from starter_v6.tests.test_v3_phase0_characterization import overlong_tag_trace


ROOT=Path(__file__).resolve().parents[2]
REFS=('d24d5ae7b02488807ab7167494496c93152bbafa',
      'bd757b493180a96b39d2c57e5901829d4d507b87',
      '4f14c6a6bf72bf4498c942dd16d815bb5787d01b',
      '35749fdf3652ba501cead2d61b96651232925164',
      '6642298534727f59740d58efba82d678c35dae98')

SCRIPT='''
import json
from dataclasses import asdict
from starter_v6.possession import FrameEvidence,possession_spells
from starter_v6.pipeline import RuntimeRestartActionDetector
from starter_v6.inference import iter_infer_e02
from starter_v6.hmm import decode,HMMConfig
out={}
fixtures={
 'long_tag': ([(10.,.1)]*3+[(10.3,2.),(10.6,2.)]+[(10.6,.1)]*4,True),
 'boundary_after_restart': ([(0.,.1)]*3+[(.3,2.),(.6,2.)]+[(-1.,.1)]*2,True),
 'unconsumed': ([(10.,.1)]*4,True),
 'fresh_gap': ([(10.,.1)]*3+[(10.3,2.),(10.6,2.),(10.6,2.)]+[(10.,.1)]*3+[(10.3,2.),(10.6,2.)],[True]*5+[False]+[True]*5),
 'half_restart': ([(10.,.1)]*3+[(10.3,2.),(10.6,2.)]+[(10.,.1)]*3+[(10.3,2.),(10.6,2.)],True),
 'live_tag': ([(10.+.1*i,2.5) for i in range(5)],True),
 'outlier': ([(80.,30.),(-1.1,30.),(80.,30.)],False),
 'reliable': ([(.1,30.),(-1.1,30.),(.1,30.)],False),
 'recovery': ([(80.,30.),(-1.1,30.),(-1.1,0.),(None,None)],False),
 'inplay_jump': ([(10.,30.),(80.,30.),(10.,30.)],False),
 'missing': ([(10.,1.),(None,None),(None,None),(10.,1.)],False)}
for name,(motion,context) in fixtures.items():
 detector=RuntimeRestartActionDetector()
 fs=[detector.observe(FrameEvidence(i,2 if name=='half_restart' and i>=5 else 1,None if x is None else (x,10.),(),s,context[i] if isinstance(context,list) else context)) for i,(x,s) in enumerate(motion)]
 rs=list(iter_infer_e02(fs));ls=['X']*len(rs)
 for half in (1,2):
  ids=[i for i,r in enumerate(rs) if r.emission.half==half]
  decoded=decode([rs[i].emission for i in ids],config=HMMConfig())[0]
  for i,label in zip(ids,decoded):ls[i]=label
 out[name]={'labels':''.join(ls),'spells':possession_spells(ls),
 'cues':[r.inference.dead_ball_evidence.cues for r in rs],
 'confirmed':[r.inference.dead_ball_evidence.confirmed for r in rs],
 'hard':[r.inference.dead_ball_evidence.hard_evidence for r in rs],
 'memory':[r.inference.dead_ball_evidence.source for r in rs],
 'emissions':[[r.emission.home,r.emission.away,r.emission.dead] for r in rs],
 'team':[asdict(r.inference.team_evidence) for r in rs],
 'quality':[asdict(r.features.quality) for r in rs]}
print(json.dumps(out))
'''


def historical(ref):
    with tempfile.TemporaryDirectory(prefix='v3-ablation-') as folder:
        archive=subprocess.run(['git','archive',ref],cwd=ROOT,capture_output=True,check=True)
        subprocess.run(['tar','-x','-C',folder],input=archive.stdout,check=True)
        return json.loads(subprocess.check_output([sys.executable,'-B','-c',SCRIPT],cwd=folder))


class Phase6AblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates=[historical(ref) for ref in REFS]

    def test_A1_persistence_intervention_and_controls(self):
        kinds=['live']*4+['stop']*3+['missing']*3+['restart']+['live']*4
        on,ls=run(kinds,25);off,old=run(kinds,0)
        self.assertEqual(''.join(ls),'HHHHDDDDDDHHHHH')
        self.assertEqual(''.join(old),'HHHHDDDHHHHHHHH')
        self.assertGreater(on[7].emission.dead,off[7].emission.dead)
        self.assertFalse(on[7].inference.dead_ball_evidence.confirmed)
        self.assertTrue(all(r.emission.dead==0 for r in on[10:]))
        for kinds in (['live']*4+['missing']*30+['live']*4,['missing']*30):
            a,_=run(kinds,25);b,_=run(kinds,0)
            self.assertEqual([r.emission for r in a],[r.emission for r in b])
        a,_=run(['stop']*3+['missing']*30,25)
        self.assertAlmostEqual(a[28].emission.dead,1/3)
        a,_=run(['stop']*3+['missing']*2,25,[1,1,1,2,2])
        self.assertTrue(all(r.emission.dead==0 for r in a[3:]))

    def test_A2_adjacent_context_correction(self):
        old,new=self.candidates[:2]
        self.assertEqual(old['long_tag']['labels'],'DDDHHDDDD')
        self.assertEqual(new['long_tag']['labels'],'DDDHHHHHH')
        self.assertEqual(old['long_tag']['emissions'][6],[.0050000000000000044,.0050000000000000044,.99])
        self.assertEqual(new['long_tag']['emissions'][6],[.5,.5,0.])
        self.assertEqual(old['long_tag']['team'],new['long_tag']['team'])
        for name in ('boundary_after_restart','unconsumed','live_tag','reliable','missing','fresh_gap','half_restart'):
            self.assertEqual(old[name],new[name])

    def test_A3_adjacent_boundary_correction(self):
        old,new=self.candidates[1:3]
        self.assertEqual(old['outlier']['labels'],'HDH')
        self.assertEqual(new['outlier']['labels'],'HHH')
        self.assertEqual(old['outlier']['emissions'][1],[0.,0.,1.])
        self.assertEqual(new['outlier']['emissions'][1],[1/3,1/3,1/3])
        self.assertTrue(new['recovery']['confirmed'][2])
        self.assertFalse(new['recovery']['confirmed'][1])
        for name in ('reliable','long_tag','inplay_jump','missing','unconsumed'):
            self.assertEqual(old[name],new[name])

    def test_A4_isolated_action_input_is_redundant(self):
        fs,on,labels=overlong_tag_trace()
        # Input intervention after the real adapter: preserve motion, ownership,
        # context and its consumption while removing only the action field.
        off=list(iter_infer_e02(replace(f,restart_action=None) for f in fs))
        self.assertEqual(on[3].inference.dead_ball_evidence.live_score,.9)
        self.assertEqual(off[3].inference.dead_ball_evidence.live_score,.7)
        self.assertEqual([r.emission for r in on],[r.emission for r in off])
        self.assertEqual(''.join(decode([r.emission for r in off],config=HMMConfig())[0]),labels)
        self.assertTrue(all('confirmed_stoppage_memory' not in r.inference.dead_ball_evidence.source for r in off[3:]))
        # Clear both action and consumption only as a second, MULTI-FIELD input
        # intervention. This is not an isolated runtime-detector ablation.
        multi=list(iter_infer_e02(replace(f,restart_action=None,restart_context_consumed=False) for f in fs))
        self.assertEqual(''.join(decode([r.emission for r in multi],config=HMMConfig())[0]),'DDDHHDDDD')
        from starter_v6.tests.test_v3_context_consumption import trace
        from starter_v6.possession import PlayerEvidence
        fs,on,labels=trace([(None,None)]*2+[(10.3,2.),(10.6,2.)],
                          players=(PlayerEvidence('H',10.2,10.,1.),))
        self.assertEqual(fs[2].restart_action,'restart_reappearance')
        off=list(iter_infer_e02(replace(f,restart_action=None) for f in fs))
        self.assertEqual([r.emission for r in on],[r.emission for r in off])
        self.assertFalse(any(r.inference.dead_ball_evidence.confirmed for r in on))

    def test_C2_C3_C4_identical_synthetic_execution(self):
        self.assertEqual(self.candidates[2],self.candidates[3])
        self.assertEqual(self.candidates[3],self.candidates[4])

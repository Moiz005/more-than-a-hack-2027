"""Synthetic-only ATD adapters -> production inference -> halfwise HMM -> spells.

No licensed asset loading, injected emissions, or injected confirmation states.
Coordinates use metres; source IDs are constructed as video index + 1.
"""
from dataclasses import dataclass, asdict
from typing import Optional
from starter_v6.ingestion import ATDFrame, ATDMetadata, Observation, TrackSlot
from starter_v6.pipeline import iter_frame_evidence, restart_frame_mask
from starter_v6.tag_features import iter_tag_evidence
from starter_v6.inference import iter_infer_e02
from starter_v6.hmm import decode, HMMConfig
from starter_v6.possession import possession_spells
from starter_v6.synthetic import tag_event


@dataclass(frozen=True)
class Sample:
    x: Optional[float] = 10.
    speed: Optional[float] = 1.
    owner: Optional[str] = 'H'
    half: int = 1


def obs(x, speed):
    return Observation(float('nan') if x is None else x/105.3,
                       float('nan') if x is None else 10./68.,
                       float('nan') if speed is None else speed,
                       float('nan') if x is None else x,
                       float('nan') if x is None else 10.,
                       x is not None, speed is not None)


def event(start, end, kind='Free Kick', code='SET PIECES'):
    return tag_event(code,start,end,tag_type=kind)


def live(n=4, owner='H', x=10., half=1, speed=1.):
    return [Sample(x,speed,owner,half)]*n


def setup(n=3,x=10.,half=1):
    return [Sample(x,.1,None,half)]*n


def gap(n,half=1):
    return [Sample(None,None,None,half)]*n


def delivery(owner='H',x=10.,half=1):
    return [Sample(x+.3*i,7.5,owner,half) for i in range(1,5)]


def lifecycle(samples, events=()):
    slots=tuple(TrackSlot(i,str(i),str(i),'H' if i<5 else 'A') for i in range(10))
    metadata=ATDMetadata(('h','a'),('Home','Away'),slots,105.3,68.)
    raw=[]
    for i,s in enumerate(samples):
        players=[]
        for slot in slots:
            # Distinct nearby tracks provide full synthetic coverage. Unknown
            # setup/missing frames have invalid player positions explicitly.
            px=None if s.owner is None or s.x is None else s.x+(.1+.3*(slot.index%5) if slot.team==s.owner else 8.+slot.index%5)
            players.append(obs(px,1.))
        raw.append(ATDFrame(i+1,i,tuple(players),obs(s.x,s.speed)))
    frames=list(iter_frame_evidence(raw,metadata,bytearray(s.half for s in samples),
                                   restart_frame_mask(events,len(samples))))
    tags=iter_tag_evidence(events,len(samples))
    results=list(iter_infer_e02(frames,tag_evidence=tags))
    assert [r.emission.frame for r in results]==list(range(len(samples)))
    labels=['X']*len(samples)
    for half in (1,2):
        ids=[i for i,r in enumerate(results) if r.emission.half==half]
        decoded,_=decode([results[i].emission for i in ids],config=HMMConfig())
        for i,label in zip(ids,decoded):labels[i]=label
    rows=[]
    for i,r in enumerate(results):
        dead=r.inference.dead_ball_evidence
        rows.append(dict(frame=i,half=frames[i].half,ball=frames[i].ball_xy,
                         speed=frames[i].ball_speed_mps,players=[asdict(p) for p in frames[i].players],
                         quality=asdict(r.features.quality),tag=asdict(tags[i]),
                         restart_action=frames[i].restart_action,
                         consumed=frames[i].restart_context_consumed,
                         evidence=asdict(dead),parent=r.inference.label,
                         emission=asdict(r.emission),label=labels[i]))
    # Split halves explicitly, even if adjacent synthetic halves have same team.
    spells=[]
    start=0
    while start<len(samples):
        end=start+1
        while end<len(samples) and samples[end].half==samples[start].half:end+=1
        if samples[start].half:
            spells.extend((t,a+start,b+start) for t,a,b in possession_spells(labels[start:end]))
        start=end
    return dict(labels=''.join(labels),spells=spells,rows=rows)


def spell_report(expected, actual):
    """Official same-team IoU ordering and one-to-one greedy matching, synthetic only."""
    overlaps=[]
    for i,(t,a,b) in enumerate(expected):
        for j,(u,c,d) in enumerate(actual):
            intersection=max(0,min(b,d)-max(a,c)+1)
            if t==u and intersection:
                overlaps.append((intersection/(b-a+1+d-c+1-intersection),i,j))
    overlaps.sort(key=lambda x:(-x[0],x[1],x[2]))
    used_e=set();used_a=set();pairs=[]
    for iou,i,j in overlaps:
        if iou>=.5 and i not in used_e and j not in used_a:
            used_e.add(i);used_a.add(j)
            pairs.append(dict(iou=iou,start_offset=actual[j][1]-expected[i][1],
                              end_offset=actual[j][2]-expected[i][2]))
    split=sum(max(0,sum(t==u and min(b,d)>=max(a,c) for u,c,d in actual)-1)
              for t,a,b in expected)
    merged=sum(max(0,sum(t==u and min(b,d)>=max(a,c) for t,a,b in expected)-1)
               for u,c,d in actual)
    return dict(expected_H=sum(t=='H' for t,_,_ in expected),expected_A=sum(t=='A' for t,_,_ in expected),
                actual_H=sum(t=='H' for t,_,_ in actual),actual_A=sum(t=='A' for t,_,_ in actual),
                matched=len(pairs),unmatched_expected=len(expected)-len(used_e),
                unmatched_actual=len(actual)-len(used_a),false_splits=split,missed_splits=merged,
                merged_neighbors=merged,pairs=pairs)

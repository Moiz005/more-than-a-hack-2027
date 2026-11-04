# TacticalFusion V3 P0 protection manifest

## Protected baseline

- Baseline checkout: `/Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027`
- Protected tag: `e04-v3-g8-release`
- Protected commit: `9fd0277a23258a448e0863b33d646c8540070c50`
- Research branch: `experiment/e04-v3-visual-possession`
- Research worktree: `/Users/moiz/Desktop/Metrica-Sports-Hackathon-visual-possession-v3`
- Baseline status at isolation: clean, detached, exact protected commit.

The baseline was not switched, reset, edited, or used as the research working
directory. The research worktree was created with `git worktree add -b` directly
from the protected full SHA.

## Artifact availability

The historical release record documents CSV SHA256
`d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`, but the
protected CSV is not present in this isolated worktree. Status: **NOT
AVAILABLE**. No replacement or fabricated verification artifact was created.
Licensed match assets are also absent; only `data/README.md` exists.

## Ignored-output proof

`.gitignore` ignores `.local-checkpoints/`, licensed `data/*`, prediction files,
submission files, and restricted diagnostics. P0 created the local directory
`.local-checkpoints/tacticalfusion-visual/` only for private audit metadata and
kept it outside the Git index. It contains no match-derived rows, media, or
frame-level output.

## Safe rollback / removal procedure

Rollback is by preserving the baseline checkout and returning to the protected
tag when explicitly authorized:

```sh
git -C /Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027 \
  rev-parse e04-v3-g8-release^{commit}
git -C /Users/moiz/Desktop/Metrica-Sports-Hackathon/more-than-a-hack-2027 \
  status --short --branch
```

Do not run cleanup automatically. Before removing the research worktree, inspect
its status and preserve any uncommitted work or commits. Only after explicit
authorization may an operator remove the worktree and branch. The protected
baseline and tag must remain intact.

## P0 additions

Tracked additions are limited to this manifest and
`starter_v6/TFV3_P0_SOURCE_AUDIT.md`. The ignored checkpoint directory contains
only its local README. No inference code, dependencies, licensed data, public
GT-derived artifact, or submission was added.

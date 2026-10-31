# V3 local reproduction and recovery

Use a compliant local machine with the licensed inputs. Do not send them to
hosted tools. Obtain the entire repository history and tags, not only v6 files:
historical oracle tests intentionally resolve prior commits through Git.

## Exact source and environment

Preserve existing work, then use a fresh clone and detach at
`e04-v3-g8-release` (or the exact proposed commit before tagging).
Verify `git rev-parse HEAD`, `git status --porcelain` and the source/config hashes
in V3_RELEASE_MANIFEST.md. Never reset an unrelated dirty working tree.

Use CPython 3.11.16. For a new environment, create `.venv` and install
`python -m pip install -r starter_v6/requirements-release.txt`.
The release verification reuses the existing verified environment; it does not
claim a new installation from an empty package cache was tested.
Compare installed distribution versions with V3_RELEASE_ENVIRONMENT.json.

Point MTAH_DATA_DIR to the licensed bundle root (the directory containing
tactical/). Fingerprint atd_meta, atd_raw and smart_tagging privately using
games.asset_paths and starter_v6.provenance.file_sha256. Do not print data.
Compare with the private historical and release input manifests.

## Checks and two independent runs

Run from the clean repository root. The output directories must not exist:

```sh
.venv/bin/python -B -m unittest discover -s starter_v6/tests -p 'test*.py'
.venv/bin/python -B -m starter_v6.run_e04 --self-check

.venv/bin/python -B -m starter_v6.run_e04 \
  --config starter_v6/config.example.json --data-dir "$MTAH_DATA_DIR" \
  --checkpoint-root .local-checkpoints/v3/phase8/release_candidate/run1 \
  --output .local-checkpoints/v3/phase8/release_candidate/run1/submission.csv \
  --diagnostics .local-checkpoints/v3/phase8/release_candidate/run1/diagnostics.json \
  --metadata .local-checkpoints/v3/phase8/release_candidate/run1/metadata.json

.venv/bin/python -B -m starter_v6.run_e04 \
  --config starter_v6/config.example.json --data-dir "$MTAH_DATA_DIR" \
  --checkpoint-root .local-checkpoints/v3/phase8/release_candidate/run2 \
  --output .local-checkpoints/v3/phase8/release_candidate/run2/submission.csv \
  --diagnostics .local-checkpoints/v3/phase8/release_candidate/run2/diagnostics.json \
  --metadata .local-checkpoints/v3/phase8/release_candidate/run2/metadata.json

.venv/bin/python evaluation/validate_submission.py .local-checkpoints/v3/phase8/release_candidate/run1/submission.csv
.venv/bin/python evaluation/validate_submission.py .local-checkpoints/v3/phase8/release_candidate/run2/submission.csv
shasum -a 256 .local-checkpoints/v3/phase8/release_candidate/run1/submission.csv .local-checkpoints/v3/phase8/release_candidate/run2/submission.csv
cmp .local-checkpoints/v3/phase8/release_candidate/run1/submission.csv .local-checkpoints/v3/phase8/release_candidate/run2/submission.csv
```

The optional local inventory test uses data/tactical directly; a local ignored
symlink to the authorized tactical folder enables it in the isolated checkout.
Without that asset it is explicitly skipped; do not misreport it as passing.
Symlink .venv to the verified local environment only for same-machine audit.
Neither symlink belongs in Git.

Expected CSV SHA256:
`d1604474717565a460d30bdef271d4e6e9b6c088c00bec84f6ef3d97a35f74ae`.
Verify header/row order/labels, published half mask, inputs, source/config hashes,
clean metadata revision and byte equality. Record actual logs and commands in
ignored local paths. A mismatch blocks tagging until provenance is understood;
never tune the model to recover a hash.

## Freeze, artifact and rollback

Only after all G8 requirements pass, verify the intended tag is unused and make
an annotated tag with no force option on the exact clean-checkout commit.
Verify its peeled target and unchanged historical refs. Save the exact resolved
commit/tag and a SHA256-identical stable submission copy in the private record.
Use exclusive creation/read-only file permissions to prevent ordinary overwrite.
Git tags are locally protected by policy, not a server-enforced write-once store.

Restore the whole frozen tree with `git switch --detach e04-v3-g8-release`.
Primary fallback: `git switch --detach e04-v3-phase0-persistence-baseline`.
Verified v2 fallback: `git switch --detach e04-v2-g8-final-verified`.
Preserve existing work and prior outputs before any checkout.

Phase 9 requires separate authorization. Confirm team naming, public repository
availability and submission-form access then; Phase 8 neither pushes nor uploads.

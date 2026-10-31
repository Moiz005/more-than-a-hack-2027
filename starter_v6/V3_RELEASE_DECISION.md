# V3 Phase 8 release decision

Select the C4 executable model at `6642298534727f59740d58efba82d678c35dae98`,
carried forward through Phase 6 `ee57304922ff29aa9e3372e1603510669d5d8d56`
and this release-preparation tree. Phase 7 is SKIPPED. No production source,
threshold, configuration or HMM change is authorized by this freeze.

The intended unique annotated tag is `e04-v3-g8-release`. Its creation is
conditional on successful clean-checkout paired reproduction and validation.
Resolve the final commit with `git rev-parse e04-v3-g8-release^{commit}`;
the private verification record binds that commit to the exact output. This
document does not preclaim that the subsequent full runs succeeded.

## Candidate comparison

| Candidate | Exact reference | Source/validator evidence | Known defect / disposition |
|---|---|---|---|
| Frozen E04_C7 | e04-c7-frozen, 7aa2f1b44b9db015a89d61fef797ebe83b4dadd2 | Historical entire tree and validated CSV retained; old source hashing omitted transitive v4 | Historical fallback; not stateful v3. Current 16-file v6 manifest is not its complete executed import graph |
| Verified v2 | e04-v2-g8-final-verified, 535d07d01d42264e2d9753b403c2449b912105f5 | Recorded source 5f970936063f0ff70c1170aba805f00ff220bea74373613044876bbdefd600d0; preserved clean validated run | Predates stateful/restart/persistence integration; preserve release |
| C0 | d24d5ae7b02488807ab7167494496c93152bbafa | Ledger S0/H0; preserved validated paired outputs | Stale-context and boundary-jump failures; frozen primary fallback |
| C1 | bd757b493180a96b39d2c57e5901829d4d507b87 | Ledger S1/H1; preserved validated paired outputs | Context correction verified; boundary-jump failure remains |
| C2 | 4f14c6a6bf72bf4498c942dd16d815bb5787d01b | Ledger S2/H2; preserved validated paired outputs | Both targeted corrections verified |
| C3 | 35749fdf3652ba501cead2d61b96651232925164 | Same executed source as C2; paired H2 outputs | Adds lifecycle verification |
| C4 | 6642298534727f59740d58efba82d678c35dae98 | Same executed source as C2/C3 | Adds external feasibility record; selected |
| Phase 6 | ee57304922ff29aa9e3372e1603510669d5d8d56 | Same C4 model; 187 recorded passing tests | Adds controlled causal assessment; retained in release ancestry |

Candidate tree/source/config hashes and historical artifact revisions are in
V3_CANDIDATE_LEDGER.md. Older references are inventoried, not freshly accuracy-
ranked. v2 final tag resolves to 56e71697c53461efcf415d9c615cbc0aded23299;
the distinct final-verified tag resolves to 535d07d01d42264e2d9753b403c2449b912105f5.
Neither is moved. Stateful d48ec42d23ba48584413d0b80bea68676e155818 and runtime
restart 24e7d0146ec3d9493ed318d72dde6bee130f58ec remain recoverable.

## Fresh admissible selection and historical exposure

Older local public-evaluation score artifacts exist (including pre-v3 Phase 8
directories). Their scores were neither read nor rerun for this decision.
Existing files were preserved. This demonstrates historical exposure existed;
it cannot prove that every earlier decision was free of score influence.

This fresh release decision uses only audited source differences, the original
invented counterexamples, preserved negative controls, lifecycle invariants,
source/config identity, test results, validation and deterministic reproduction.
The default C4 choice was specified before Phase 8 verification and is unchanged.
No score, D prevalence, match-duration histogram or synthetic F1 ranking enters
the decision. This documents independent grounds for current selection without
claiming an unobservable clean historical decision process.

Current model fixes documented counterexamples without additional production
complexity over C2. C0 remains a fallback because it is frozen and recoverable,
not because it has proven higher accuracy. A failed release gate requires
diagnosis or a verified fallback, never threshold tuning inside this phase.

No admissible independent other-match accuracy evaluation was completed.
Full-match spellF1 superiority is unknown. IDSSE remains an unacquired conditional
lead; no external acquisition or Phase 7 experiment is part of this release.

## Recovery and next step

After preserving unrelated work, restore the complete release with
`git switch --detach e04-v3-g8-release`. Primary fallback:
`git switch --detach e04-v3-phase0-persistence-baseline` (d24d5ae7b02488807ab7167494496c93152bbafa).
Assessment rollback: `git switch --detach 6642298534727f59740d58efba82d678c35dae98`.
Phase 9 may begin only after all G8 evidence is recorded and separately authorized.
No external upload or publication is performed by Phase 8.

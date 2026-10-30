
## Local mock inspection threats

| Threat | Control |
|---|---|
| Navigation to a remote form or third-party resource | Deny external network access and limit the harness to a known local fixture |
| Accidental typing into a form | Do not expose or invoke fill/type APIs; test that they are never called |
| Accidental file disclosure | Detect file inputs structurally only; prohibit file selection and exclude filenames and paths from output |
| Accidental submission | Detect submit-like elements without clicking; hard-block submit actions and expose a `submit_blocked` proof flag |
| Candidate-data leakage into reports | Build artifacts only from an allowlist of structural metadata |
| Unsafe policy bypass | Reject artifact serialization unless all safety invariants pass |
| Runtime artifact leakage into Git | Ignore generated artifact output; use sanitized static fixtures only for tests |

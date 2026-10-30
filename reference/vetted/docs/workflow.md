
## Local mock inspection workflow

1. Load the bundled synthetic local fixture.
2. Start headed Chromium with external network access blocked.
3. Inspect form structure without filling, selecting files, clicking, or submitting.
4. Classify controls as text, select, checkbox/radio, file, or submit-like.
5. Produce terminal-only inspection results.
6. Serialize a sanitized review artifact after safety validation.
7. Stop the browser.

A failed safety check terminates the run before artifact creation. No later workflow stage may treat an inspection artifact as authorization to fill fields, upload files, access a live site, or submit an application.

## Scope gate

The local mock artifact milestone is complete only when:

- The synthetic fixture control inventory is deterministic.
- Safety flags are verified in automated tests.
- Artifacts exclude mutable values and candidate data.
- Unsafe policy states are rejected.
- No browser fill, upload, click, submit, or external navigation APIs are invoked.

Live-form support, filling, upload, and submission are outside this milestone.

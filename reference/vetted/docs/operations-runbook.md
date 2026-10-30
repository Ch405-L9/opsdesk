
## Run local mock inspection

Run the registered local mock inspection command:

```bash
web-agent inspect-local-mock
```

Expected behavior:

- A headed Chromium window briefly opens.
- The synthetic fixture is rendered locally.
- The terminal reports the discovered control count.
- File and submit controls are detected but not activated.
- The browser closes after inspection.
- The run reports that network access, filling, uploading, and submission are blocked.

Expected safety result:

```text
Network: blocked
Fill: blocked
Upload: blocked
Submission: blocked
NO APPLICATION HAS BEEN SUBMITTED.
```

Stop and investigate if any run attempts external navigation, persists a field value, shows a selected local file, invokes a click/fill/upload API, or reports a submitted state.

## Validate inspection artifact

Before accepting an artifact for review, verify:

- It parses as JSON.
- It identifies the source as a synthetic local fixture.
- `external_network_accessed` is `false`.
- `fill_blocked`, `upload_blocked`, and `submit_blocked` are all `true`.
- `application_submitted` is `false`.
- It includes structural control metadata only.
- It includes no candidate data, field values, file paths, credentials, cookies, tokens, or browser session data.

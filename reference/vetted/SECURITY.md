
## Local inspection artifacts

Inspection artifacts are restricted to sanitized structural metadata from synthetic local fixtures.

Artifacts must not contain candidate data, resumes, contact details, form values, selected filenames, local filesystem paths, authentication material, cookies, browser storage, request headers, session identifiers, or live-site content.

A generated artifact that may include any protected data must be treated as a security incident: do not commit it, revoke or remove exposed credentials if applicable, delete the artifact from shared locations, and report it through the repository's security process.

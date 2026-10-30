"""Capture ingestion.

Turns a manually captured listing, in the approved `JOB_CAPTURE_TEMPLATE.md` format, into a
`NormalizedJob`. Text in, value out: no filesystem read, no network call, no environment read,
and no persistence. The caller supplies the text, normally from standard input.

Absent fields become `UNKNOWN` and nothing is guessed, per the template's own import rule.
A malformed value raises rather than degrading quietly, because silently coercing an
unparseable value is a guess.

Contact data is discarded. `public_recruiter_or_contact` has no destination field by design
(D-9), so it cannot survive import.
"""

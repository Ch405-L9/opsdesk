# Candidate Evidence Policy

## Purpose

This project creates local, traceable candidate evidence for human-reviewed job-application preparation. It uses verified source material to generate drafts and review packages. It does not submit applications.

## Canonical evidence sources

Initial candidate evidence may be derived from a locally stored source résumé referenced only through the untracked `SOURCE_RESUME_PATH` setting. The actual source résumé and its absolute path must never be committed, logged in terminal reports, uploaded by default, or embedded in generated artifacts.

Additional sources such as project repositories, portfolio case studies, verification reports, or certifications require explicit review before indexing.

## Atomic evidence requirements

Every indexable claim must be stored as an atomic evidence record with:

- `evidence_id`
- `category`
- `factual_statement`
- `source_classification`
- `approved_for_external_use`
- `confidence`
- `tags`

Metrics, dates, employers, locations, project names, and scope must be preserved exactly as verified. Every generated factual claim must reference its supporting evidence ID or IDs.

## Allowed initial categories

- Identity and approved public professional links
- Professional positioning
- Applied AI and retrieval experience
- Software and automation experience
- Quality, reliability, troubleshooting, and release-validation experience
- Systems and networking experience
- Delivery, communication, and implementation experience
- Project evidence
- Work experience
- Education and training, with completion status preserved exactly

## Prohibited inferences

The system must not infer, create, state, or imply:

- A completed degree when evidence states only coursework toward a degree
- Games-industry experience
- Game QA leadership
- Formal people management
- A formal QA certification
- Unverified years of experience
- Unverified skills, credentials, metrics, dates, job history, or project outcomes
- Work authorization, sponsorship needs, compensation, availability, schedule, relocation, travel preferences, or legal eligibility
- Disability, veteran-status, demographic, criminal-history, or background-check responses

## Private inputs

Sensitive answers belong only in an untracked local private-input file. They are not indexed by default and must be represented as `NEEDS_USER_INPUT` in job-specific plans and reviews.

## External-use rule

Evidence retrieval is advisory. Retrieval does not authorize an unsupported claim. The system must stop with a blocker or request user input when required evidence is missing.

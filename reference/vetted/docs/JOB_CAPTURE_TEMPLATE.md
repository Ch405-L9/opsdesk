---
document_id: job-capture-template
title: Permitted Local Job Capture Template
version: 1.0.0
status: approved_for_wellfound_mvp
last_reviewed: 2026-09-25
owner: the candidate
change_policy: human_approval_required
---

# Job Capture Template

Use this template only for content you manually copied, received through a permitted alert/export, or otherwise obtained lawfully and in compliance with the source platform’s rules. Do not use it as justification for prohibited scraping or credential sharing.

```markdown
---
source_platform: wellfound
source_url: ""
import_method: manual_copy_paste
captured_at: "YYYY-MM-DDTHH:MM:SS-04:00"
stated_posting_date: "UNKNOWN"
owner_notes: ""
---

# Job identity

job_title: ""
company_name: ""
company_website: "UNKNOWN"
official_careers_url: "UNKNOWN"
company_description: ""
company_stage_or_size: "UNKNOWN"

# Work arrangement

employment_type: "UNKNOWN"
location_text: ""
work_arrangement: "UNKNOWN"
remote_details: "UNKNOWN"
state_restrictions: "UNKNOWN"
time_zone_restrictions: "UNKNOWN"
travel_requirements: "UNKNOWN"
relocation_status: "UNKNOWN"
work_authorization_requirements: "UNKNOWN"
clearance_requirements: "UNKNOWN"

# Compensation

base_salary_min_usd: "UNKNOWN"
base_salary_max_usd: "UNKNOWN"
total_compensation: "UNKNOWN"
bonus: "UNKNOWN"
equity: "UNKNOWN"
hourly_rate_min_usd: "UNKNOWN"
hourly_rate_max_usd: "UNKNOWN"
contract_term: "UNKNOWN"
benefits: "UNKNOWN"

# Role content

responsibilities: |


required_qualifications: |


preferred_qualifications: |


education_requirements: |


years_of_experience: "UNKNOWN"
required_technologies: |


# Hiring and application

public_recruiter_or_contact: "UNKNOWN"
application_instructions: "UNKNOWN"

# Raw listing text

raw_listing_text: |
  PASTE THE COMPLETE JOB DESCRIPTION HERE.
```

## Import requirements

Every capture requires:

- Platform/source name.
- Original URL, if available.
- Capture timestamp.
- Import method.
- Complete raw listing text whenever practical.

The importer must preserve source text, mark absent values `UNKNOWN`, and avoid guessing compensation, company legitimacy, work arrangement, seniority, or relocation.

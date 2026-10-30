# BADGR Site Audit

Local command-line wrapper around Lighthouse.

## Commands

- `siteaudit doctor`: check Chrome and report-directory access.
- `siteaudit audit https://example.com`: run a mobile audit.
- `siteaudit reports`: print the report directory.
- `siteaudit help`: show usage.

## Output

Each successful run saves:
- lighthouse.html: full Lighthouse report.
- lighthouse.json: raw Lighthouse results.
- summary.json: scores and explicit analytics status.

Reports are stored under:
~/.local/share/badgr-siteaudit/reports/

## Limitations

This initial version has no browser dashboard or Matomo adapter.
It does not measure real visitor traffic, purchases, or cart abandonment.
Lighthouse scores are lab measurements, not conversion measurements.
Audit only sites you own or are authorized to test.
Audit navigation can appear in the website's logs or analytics.
Reports can contain URLs or page content; review before sharing.

## Installation and removal

Project dependencies are local; package-lock.json records resolved versions.
npm link exposes the siteaudit command in the active npm prefix.
With a Node version manager, switching Node versions may require relinking.

To remove the linked command:
npm uninstall -g badgr-siteaudit

Keep or remove the project and reports separately.

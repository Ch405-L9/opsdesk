# OpsDesk user manual

OpsDesk keeps your **leads**, **government bids**, **jobs** and **follow-ups** in one place on your own computer.

Three promises:
- Nothing runs on its own.
- Nothing is sent or submitted for you.
- Your edits are never overwritten.

---

## 1. Install (one time)
You need Python 3.12 and `uv` (https://docs.astral.sh/uv/).

```bash
cd opsdesk
uv tool install .          # makes the `opsdesk` command available everywhere
opsdesk --version
```

Updating later: `git pull`, then `uv tool install . --force`.

## 2. Set up your profile (2 minutes)
```bash
opsdesk init
```
It asks for:
- your business name and your name (used to sign drafts);
- your city and state;
- the industries you sell to;
- your NAICS codes (for bids). Web and IT shops usually use `541511` and `541519`.

Run it again any time to change answers.

Optional: set a minimum salary and your certifications:
```bash
opsdesk init --salary-min 60000 --certifications wosb
```
Certifications are self-declared; OpsDesk never assumes you have one.

Check everything:
```bash
opsdesk doctor
```

### Try it first with sample data
```bash
opsdesk demo
```
This loads fake businesses and a fake job so you can practice. Sample items are tagged **demo**.

## 3. Your daily routine (5 minutes)
```bash
opsdesk today      # overdue (red), due today (yellow), next 7 days
```
Then, for each item:

| You want to… | Type |
|---|---|
| Schedule a follow-up | `opsdesk follow "Bella Spa" +3d "call about quote"` |
| Add a note | `opsdesk note "Bella Spa" "left voicemail"` |
| Mark it done | `opsdesk done "Bella Spa"` |
| Push it out a few days | `opsdesk snooze "Bella Spa" 3` |
| Change status | `opsdesk status "Bella Spa" contacted` |
| Set priority | `opsdesk priority "Bella Spa" high` |
| Tick "contacted" | `opsdesk contacted "Bella Spa"` |
| See everything about it | `opsdesk show "Bella Spa"` |

- **Naming an item:** type part of its name, like `"bella"`. If more than one item matches, OpsDesk lists them; then use the full key, like `lead:bellaspa.com`.
- **Dates:** `2026-11-03`, `today`, `tomorrow`, `+3d`, `+2w`, or a weekday such as `mon` or `fri`.
- **Statuses:** run `opsdesk statuses` to see them all. Leads go new → contacted → replied → meeting → proposal → won or lost.

## 4. Leads: find local businesses to pitch
```bash
opsdesk leads find dentists in Austin TX --demo     # practice, free
opsdesk leads find dentists in Austin TX            # real search
```
- A **real search** needs a Google Places key: `opsdesk keys set google_places`.
- It **costs 1 call**, and OpsDesk asks you to type `spend` first. You get 1,000 free calls a month; OpsDesk stops itself at 800.
- Repeating the same search within 14 days is **free**: it uses the saved results.
- Check what's left: `opsdesk leads budget`.

Then:
```bash
opsdesk leads list                 # your leads, best first
opsdesk leads audit "Bella Spa"    # Google Lighthouse speed/SEO check (needs a PageSpeed key, 1 call)
opsdesk leads draft "Bella Spa"    # cold email + phone opener, from measured facts
```
Drafts are drafts. Copy the email into your own mail app and edit it before you send. OpsDesk never sends email.

**Tip:** businesses with **no website** score high. They're usually your easiest pitch.

## 5. Bids: find government buyers
```bash
opsdesk bids fetch     # free public data (USAspending), no key needed
opsdesk bids rank      # best opportunities first
opsdesk bids report    # writes a Markdown report
```
- **Fit** is "look at this first", **not** your chance of winning.
- **Lanes:**
  - *sb_set_aside*: small-business set-aside, a good fit.
  - *subcontract*: a big contract; offer to subcontract to the company that holds it.
  - *blocked*: needs a certification you haven't declared.
- Awards ending in 3–12 months are **recompetes**. Watch SAM.gov for a "sources sought" notice on them.

## 6. Jobs and your resume evidence
**Step 1: write down your proof once.**
```bash
opsdesk resume init     # creates your private evidence file with examples
```
Open the file it names and replace the examples with **true** facts. For example:
- *skill:* Python
- *project:* rebuilt a site, Lighthouse score went from 41 to 96

Never put an email address or phone number in it.

**Step 2: save a job.**
```bash
opsdesk jobs template > job.md     # fill in title, company, url, required skills…
opsdesk jobs add job.md            # saves it and assesses it
```
The assessment shows:
- **technology alignment** (0–100);
- salary against your minimum;
- whether the work arrangement fits;
- blockers, such as a clearance;
- **gaps**: skills you have no proof for. Don't claim those.

**Step 3: resume bullets that cite your proof.**
```bash
opsdesk resume draft "Web Developer"
```
Every bullet is one of your own evidence statements, with its ID.

**Step 4: apply on the employer's site yourself, then record it.**
```bash
opsdesk jobs applied "Web Developer" --note "applied on company site"
```
This saves a dated **receipt**: a copy of the posting exactly as it read when you applied.

## 7. The spreadsheet
```bash
opsdesk export
```
This creates `OpsDesk.xlsx`. Run `opsdesk where` to find the exports folder. It contains:
- a **Today** sheet;
- **Leads**, **Bids** and **Jobs** sheets.

On each sheet:
- **Yellow columns are yours:** Status, Priority, Done ☐/☑, Contacted ☐/☑, Follow-up Date, Follow-up Note and Notes. Use the dropdowns.
- **Colors:** overdue rows turn **red**, due today turns **yellow**, and closed items go grey.
- **Names and links are clickable.**

**Edit freely, then save and close the file**, and run `opsdesk export` again. OpsDesk:
1. reads only the cells **you changed**;
2. adds new notes to the bottom, instead of replacing old ones;
3. keeps a backup copy of the old file (`OpsDesk.prev.xlsx`).

If the file is still open in Excel, OpsDesk waits and tells you to close it. To pull your edits in without making a new file, run `opsdesk import-edits`.

The navy columns come from the tools. Edits there are ignored; change those things in OpsDesk instead.

## 8. The dashboard
```bash
opsdesk dash
```
This opens http://127.0.0.1:8765 in your browser. Only your computer can reach it.

| Page | What it's for |
|---|---|
| Today | Overdue and due items, with one-click **Done** and **+3 days** |
| Leads, Bids, Jobs | Filter by status, search (press **/**), click headers to sort, click a name for details |
| Item page | Change status, priority, follow-up, Contacted and Done; add notes; see history |
| Leads → Find leads | Sample data, or Google Places after you type `spend` |
| Jobs → Add a job | Paste a capture |
| Resume | Your evidence |
| Activity | Every change, and who made it |
| Settings | Profile, keys, quota |
| Export workbook (top right) | Makes the spreadsheet |

Stop the dashboard with **Ctrl+C** in the terminal.

## 9. Keys, files and backups
| Task | How |
|---|---|
| Add a key | `opsdesk keys set google_places` or `opsdesk keys set pagespeed`. Typing is hidden, and the key is stored in a private file. |
| See which keys are set | `opsdesk keys list` (never shows the values) |
| Find your files | `opsdesk where` |
| Back up | `opsdesk backup` (copies your database safely) |
| See what happened | `opsdesk activity` |
| Get computer-readable output | Add `--json` to `today`, `show` and the `list` commands |

**Extra safety on Google's side (recommended).** In Google Cloud Console, go to Places API → Quotas and cap "SearchTextRequest per day" at about **30**. Google then refuses calls beyond your free allowance, even if something else uses your key.

## 10. Troubleshooting
| Message | Fix |
|---|---|
| "Add NAICS codes first" | `opsdesk init --naics 541511` |
| "This search uses 1 Places call… Re-run with --yes" | You ran it from a script. Add `--yes` only if you mean it. |
| "No item matches…" / "N items match…" | Use more of the name, or the full key from `… list` |
| "looks open in a spreadsheet app" | Save and close the workbook, then run it again |
| "evidence.yaml is invalid" | The message names the field; fix that line |
| Anything else | `opsdesk doctor`, then `opsdesk activity` |

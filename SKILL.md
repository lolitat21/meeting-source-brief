---
name: meeting-source-brief
description: Daily pre-meeting brief that works out where every external meeting actually came from before it researches anyone. Checks every lead source every time (outsourced SDR, outbound campaigns, signal tools, events, website form last), picks the primary source by a fixed precedence, respects which source owns the account, and sends one combined brief per day. Use for "meeting brief", "who are we meeting tomorrow", "prep tomorrow's calls", "demo brief", or when a scheduled run fires.
---

# Meeting Source Brief

Before anyone joins a call, they should know how the meeting happened. A booking
link tells you how someone *scheduled*, not why they showed up. This skill finds
the real source first, then does the research.

Configuration lives in `sources.json` (copy `sources.example.json`). Nothing
company-specific belongs in this file.

The model gathers evidence. `tools/attribute.py` makes the calls that must not
drift: which meetings count, which source wins, who owns the account, whether a
personal follow-up is allowed.

---

## Step 1: The next working day

Friday and Saturday roll to Monday. Every other day is tomorrow. Brief one day only.

## Step 2: Find the meetings

List **every** event on the hosts' calendars for that day. Don't keyword-search
the calendar; titles vary and a search misses the meetings that matter most.

Write the events to a JSON list (`title`, `organizer`, `status`, `attendees` with
`email` and `response`) and filter them:

```bash
python3 tools/attribute.py --keep events.json
```

A meeting is kept when it has an attendee outside `internal_domains` (vendor staff
count as internal), nobody external has declined, it isn't cancelled or personal,
and a host attends, a vendor organized it, or the title looks like a booking.

Record for each: prospect name, every external email, start and end time in the
team's timezone, the organizer, and each attendee's response. Flag anyone who
hasn't accepted.

**Nothing kept: stop. Send nothing.**

**Dedupe.** If a brief sent in the last `dedupe_days` already covers this
prospect for this date, drop them. If someone was briefed earlier for a meeting
that has since been rebooked, include them, but write only what's new or
corrected and say so.

## Step 3: Where did this meeting come from?

For each prospect, run **every** source in `sources.json`, in order, every time.
Never stop at the first hit. People routinely show up in two or three.

- Search by email, then by name. When searching a free-text ledger, use the
  stem: `python3 tools/attribute.py --stem "<full name>"`. Vendor ledgers misspell
  surnames, and the stem is short on purpose so a dropped letter doesn't hide a
  match. Always pair it with the company.
- For each hit record the source id, the date, and the detail: the prospect's
  own words quoted verbatim, the campaign name, the signal, who drafted what.
- Pull the other people at the **same company** from each source too. That's the
  account context, and it decides who's allowed to reach out.
- Check `fallback_only` sources (the website form) only when the meeting came
  through the booking link and nothing above it matched, or you still need a
  work email.
- Count cancellations and reschedules from the inbox.

Then resolve:

```bash
python3 tools/attribute.py hits.json
```

It returns the primary source, the account owner (the highest-precedence source
with `owns_account`), whether personal outreach is allowed, every source that
touched the person, and warnings. Use its answer; don't overrule it in prose.

**A website booking from someone a vendor has been working is the vendor's meeting.**
**No hits is "unknown", never "website inbound".**

## Step 4: Research

- Enrich each person once (work email, or name plus company domain). Stay within
  `enrichment_credits_per_run`. Don't re-enrich anyone briefed within
  `reenrich_after_days`.
- Company news from the last 6 months: funding, M&A, exec changes, layoffs, earnings.
- A hard-bounced work email usually means they've changed jobs. Say so.
- Mark every figure from an enrichment tool or a web search "est.".

## Step 5: Records and follow-up

- Update the CRM record only to match what you found. Search before you create,
  so you never make a duplicate. When adding labels, write back the union of old
  and new; never replace.
- Tag a contact as website inbound **only** when that's the resolved primary source.
- Personal outreach (a connection request, a note) only when `outreach_allowed`
  is true. When it's false, say why in the brief: who owns the account.
- Never report an action as done until you've seen it land.

## Step 6: One brief for the whole day

One message to `recipients`, however many meetings there are.

```
<One line: how many meetings and where they came from.>

AT A GLANCE (times in <timezone>)
<time>  <Name>, <Title>, <Company> (<source>, <accepted / NOT accepted>)

<If an owner holds any of these accounts: "Don't contact others at <company>; <owner> owns it.">

── 1) <NAME> | <Company> | <start-end> ──

<Warnings first: not accepted, rebooked N times, touched by several sources, changed jobs.>

HOW THIS MEETING HAPPENED
Source: <primary>. <Their words, verbatim, with the date. What we sent. Reschedules.>
Prior touches: <every other source hit with dates, or "none found">
Account context: <others at the company, what they said, who owns them>

Name · Email · Title & tenure · Org · Company · Revenue (est.) · Headcount (est.)
· Stack · Recent events · Location (+ their local time) · Angles · 5 discovery questions

ACTIONS TAKEN
<per person: record changes, outreach sent / skipped and why, credits used, sources that failed>
```

Example: [`examples/brief.md`](examples/brief.md).

## Rules

- The next working day only. One brief per day, never one per prospect.
- Every source, every time. A booking link is not a source.
- `attribute.py` decides the primary source and the owner. Prose doesn't.
- Respect ownership: if a vendor owns the account, nobody else contacts anyone there.
- "Not found" or a labelled estimate, never a guess.
- If a source fails, carry on and say what failed in the brief.
- Never enter passwords or credentials anywhere.

---
title: "Automating the Grant History Reverse-Search"
date: 2026-04-12
category: Engineering
tags: [python, nonprofits, grants, automation, 990, irs]
type: blog
---

If you've ever tried to reconstruct a nonprofit's grant history from public records, you know the IRS Form 990 is both a goldmine and a dumpster fire. While an organization's own 990 shows their total revenue, the donor names in Schedule B are redacted from public view. To find out who actually gave them money, you have to "reverse-search" the filings of *other* organizations—private foundations (990-PF) and public charities (990 Schedule I)—to see where your target org appears as a recipient.

Doing this manually involves searching ProPublica’s Nonprofit Explorer, opening a dozen PDFs, hitting Ctrl+F for an EIN, and copying values into a spreadsheet. It takes hours, it's error-prone, and it’s the kind of task that makes you wonder why we haven't automated the IRS into the sun yet.

I built `fundingtrace` to turn this manual archeology into a repeatable CLI pipeline.

#### The Stack and the "Conductor"

The development of `fundingtrace` followed a two-phase AI-assisted methodology. 

1. **Phase 1: Prototyping with Claude Code + Superpowers.** I used Claude Code to scaffold the core logic—async HTTP clients for ProPublica, XML parsing for the IRS e-file S3 buckets, and a local request recorder for building test fixtures. The "Superpowers" extension allowed for rapid iteration on the fuzzy name-matching logic, which is necessary because foundations often spell recipient names like they’re typing with oven mitts.
2. **Phase 2: Planning with Gemini CLI + Conductor.** As the scope grew from a simple search script to a multi-org comparison tool, I switched to Gemini CLI using the `conductor` extension for architectural planning. This moved the "institutional knowledge" of the project into a set of `openspec/` documents (Specs, Proposals, and Tasks) that defined the exact requirements for things like funder categorization and result deduplication.

The resulting tool is a Python 3.11+ CLI built with `httpx` for async performance and `typer` for the interface. 

#### Two-Pass Search: Precise vs. Fuzzy

The most critical part of the tool is the search strategy. A simple EIN search isn't enough because many foundations leave the recipient EIN field blank in their filings. 

`fundingtrace` implements a two-pass approach:
- **Pass 1 (EIN):** Precise, high-confidence matching. If the EIN matches, we know it's our target.
- **Pass 2 (Name):** Fuzzy matching against name variants (e.g., "Example School" vs "Example School Inc."). 

We then deduplicate. If a grant appears in both, we keep the EIN-sourced record. If it only appears in the name search, we flag it for manual review with a `confidence: medium` score. It’s better to have a human check a few false positives than to miss a 0k grant because a program officer forgot to look up an EIN in 2018.

#### Results: From Hours to Seconds

The manual process that took a volunteer several hours now takes about 45 seconds. The tool fetches search results, filters for e-filed XMLs, parses the specific grant schedules, and categorizes funders (Traditional Foundation vs. DAF vs. Payment Processor) automatically.

The data is stored as flat JSON files—one per organization—which keeps things simple, diffable, and easily consumable by Pandas for generating comparison reports.

#### What’s Next?

The current version handles the "public 990 slice" of funding. The next step is integrating `USAspending.gov` to bring in federal pass-through grants, which are currently invisible to the tool. 

Until then, at least we don't have to manually Ctrl+F through 400-page PDFs anymore. My eyes, and the volunteers, thank me.

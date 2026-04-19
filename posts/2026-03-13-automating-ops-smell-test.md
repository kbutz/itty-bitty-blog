---
title: 'Automating the Ops "Smell Test" with Claude Code'
date: 2026-03-13
category: Engineering
tags: [claude-code, ops, automation, ai, grafana, redash]
---

Setting hard threshold alerts on metrics is easy enough. But anomaly detection, and more importantly deviation detection, is much harder. There's an intuitive "smell test" that an experienced operator applies to a dashboard. You just know when a trend looks slightly off, or when a previously stable baseline has subtly shifted.

The problem is that process requires an engineer to manually open Grafana and Redash every morning, squint at charts, and compare current values to a mental model of "normal." That works fine for an individual, but it breaks down quickly when you go on PTO, when the team grows and institutional knowledge dilutes, or when you simply forget to check on a Friday afternoon.

I wanted to see if I could automate this smell test. The idea: define an autonomous Ops Reviewer, give it a scope and a set of dashboards, and have it review them on a schedule, alerting us only when something actually looks wrong.

Here's how it works.

## Three files and a cron job

The system is a Python application that spawns Claude Code processes to perform structured dashboard reviews. Each review operates independently and is defined by three files in a directory:

- `review.yaml`: declares the data sources (dashboard URLs, Redash query IDs), the cron schedule, and the designated alert channels.
- `CLAUDE.md`: the system prompt. It tells the agent its role, the tools at its disposal, how to analyze the data, and the strict output format to follow.
- `calibration.md`: the learned context for this specific domain — what "normal" actually looks like here, built up through interactive operator sessions.

A scheduler process reads these definitions, runs them via APScheduler, and serves a lightweight Flask dashboard on port 8080 so we can view the run history and findings.

## Execution: headless browsing and data extraction

When a scheduled review fires, the system spawns Claude Code in headless mode (`claude --print -p "..."`).

The agent uses a Playwright-based CLI tool to interact with our SSO-protected dashboards. For Grafana, it captures screenshots and, crucially, extracts the panel legend data (Last, Max, Min, Mean values). For Redash, it grabs screenshots, extracts HTML table data, and can even run exploratory SQL queries against the data sources for deeper investigation.

The agent reads this captured data, compares it against the calibration file, and writes a structured `findings.md` that categorizes observations by severity (INFO/WARNING/CRITICAL), backs them up with specific data points, and recommends actions. A post-run script parses the findings into a SQLite database and fires off Slack notifications for anything WARNING or CRITICAL.

## Calibration

The most important design decision in this system was the calibration workflow. It's also where the interesting part lives: institutional knowledge accumulates as plain markdown.

The first time the agent runs a review, it has no context. A 78% KYC match rate might be a standard Tuesday, or it might be a catastrophic failure, depending on the provider.

Running the system with a `--calibrate` flag puts the agent into interactive mode. It captures the dashboards, presents what it sees, and asks questions: "Is this TransUnion 0% verification rate for 19K records a problem?" You explain that it's legacy data, and the agent permanently writes that rule into `calibration.md`.

The file accumulates domain knowledge in plain text. It documents that Provide A's volumes are always higher than Provider B's by design, or that a sudden data discontinuity in March was due to a new criteria code launch rather than an actual failure. After one or two interactive sessions, false positives drop to near zero.

## What works, what's fragile

We currently have seven of these reviews running in production every weekday morning, covering everything from SSN KYC match rates to decisioning service latency and background cron job throughput.

The wins:

- *Numbers beat pixels.* Initially, the agent misread chart values from screenshots. Explicitly feeding it numeric data from panel legends alongside the screenshots fixed this. It now uses numbers for hard values and screenshots purely for trend shapes.
- *Cross-referencing.* The agent checks warehouse data (Redash) against real-time logs (Grafana Loki) and only raises alerts when both sources agree, which catches things a single dashboard would miss.
- *Structured output.* Forcing the agent to write a consistent `findings.md` means we can reliably parse the results into our database.

The tradeoffs:

- *Cost and speed.* Spawning a full Claude Code session for every review isn't cheap or instant. A typical review takes 2-5 minutes.
- *Brittle tooling.* The Playwright browser tool is the weakest link. Dashboard layouts change, Grafana panels get reorganized, and SSO sessions expire (currently requiring manual re-authentication). Talking directly to the Grafana and Redash APIs would be much more robust.
- *Alert acknowledgments.* If a review flags a known spike that's still within its 7-day lookback window, there's no easy way to snooze the alert without editing the calibration file.
- *DRY-ing the prompts.* The `CLAUDE.md` files have a lot of boilerplate overlap. A templating system is the obvious next step as we scale this up.

Running UI automation inside an AI loop is fragile in the ways you'd expect. But codifying an engineer's smell test into plain text has paid off — the morning review is now something the team can trust without me.

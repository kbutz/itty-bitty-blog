---
title: "Retiring Three of My Seven AI Personas"
date: 2026-07-24
category: Engineering
tags: [ai, claude-code, agents, orchestration, personas]
type: blog
---

Back in the spring I wrote three posts about `claude-conductor`, a local tool that
runs Claude Code agents against tasks in isolated git workspaces and opens merge
requests when they're done. Since then most of the work has gone into a layer that
sits on top of the orchestrator: personas. Named agents, each with its own prompt
file, its own settings, its own tab in the web UI, that read and write a shared
markdown vault and message each other through it.

At peak there were ten of them. Two weeks ago I deleted three, along with the
workflow that chained them together. That commit removed about 5,700 lines of
Python and prompt text and added roughly 900 back. This post is about why, because
the reasoning generalizes past my particular tool.

## What the roster looked like

The personas were modeled on an engineering org, which in hindsight is the whole
problem. Each one had a title:

- **Vera**, VP of Engineering. Reviewed projects for planning and
  execution-readiness. Was the launch plan real? Was there a workflow diagram?
  Were there conductor tasks for work we'd committed to? Named gaps and assigned
  the next move.
- **Rex**, project manager. Day-to-day task flow, project state updates, Jira
  hygiene, submitting conductor tasks.
- **Sage**, software analyst. Deep repository analysis and task breakdowns.
- **Maya**, coordinator. Parsed my chat replies and routed the resulting
  directives to whichever persona needed them.
- **Quinn**, manual QA. Hands-on end-to-end test runs in a real browser.
- **Wren**, weekly recaps from Jira and GitLab activity.
- **Scribe**, note-taker.
- **Dori**, data-lake engineer. Reviews mask and DMS coverage on
  `transformations` merge requests.
- **Gimli**, Grafana dashboards.
- **Mr. Shepherd**, merge-request triage on a heartbeat.

They communicated through files. A persona wanting something from another persona
wrote a markdown file into `~/workspaces/brain/inbox/<recipient>/` named
`YYYYMMDD-HHMMSS_<sender>_<intent>_<project-slug>.md`, with frontmatter carrying
`from`, `to`, `intent`, `status`, `priority`, and a body of Context / Ask /
Acceptance / Resolution. There was a registry of legal intents:
`request_tech_analysis`, `request_task_breakdown`, `request_qa_plan`,
`request_data_lake_review`, `escalate`, `blocked`, and a matching `*_complete` for
each. On top of that sat a workflow called Team Review that ran Vera, then Rex,
then Sage if Sage had anything pending, then Vera again to refresh their verdict.

It worked. It also produced a system where answering one question of mine could
require four agent launches.

## The handoff is the expensive part

The thing I got wrong is that I treated a persona boundary as free. It isn't. It's
a serialization boundary.

When Vera decided a project needed technical analysis, they couldn't just do the
analysis. They wrote an inbox file describing what they wanted. Later — a separate
process, a separate context window, a fresh prompt — Sage woke up, read that file,
and tried to reconstruct enough of Vera's reasoning to act on it. Everything Vera
knew that didn't make it into the Ask section was gone. Then Sage wrote
`tech_analysis_complete` back, and Rex read *that* file and tried to reconstruct
what Sage had actually concluded.

Three context reconstructions, each lossy, to do one piece of work. And every one
of them was a full Opus run — reading the project, reading the topic notes,
reading the inbox thread — before it got to the part that was actually novel.

For humans, an org chart exists because no one person can hold the whole system in
their head and be available for everything at once. Neither of those constraints
applies here. One agent can hold the project's entire state. There is no
availability problem; runs are sequential anyway. So the org chart was pure
overhead — I'd modeled the coordination cost of humans without getting any of the
benefit that cost buys.

## What replaced them

**Vera folded into Rex.** The readiness checks weren't a separate *role*, they were
a separate *question* — one Rex could ask while already holding the project in
context. Rex's prompt grew a section on gates, blockers, and staleness detection.
Vera's 639-line prompt and 747-line service went away. What was lost: an
adversarial second opinion, since Rex now grades their own homework. I decided the
lossy handoff cost more than the independence bought, and I'd rather have the
disagreement come from me.

**Sage became a sub-run, not a teammate.** This is the distinction I'd have most
liked to understand up front. The analysis capability was genuinely useful; what
was useless was giving it a name, an inbox, and a tab. So it survives as a headless
call Rex makes inline:

```bash
conductor analysis run <slug> --instructions "..." --wait
```

The docstring on the new module is the whole design:

```python
"""Analysis sub-run — on-demand deep repo analysis (ex-Sage).

Launched synchronously from a Rex run (or by Kyle) via
`conductor analysis run <slug> --instructions ...`. There is no heartbeat,
no inbox protocol, and no persona tab: this is a tool, not a teammate.
"""
```

Rex decides mid-run that a gap needs grounding, spawns the sub-run, waits, reads
the doc it produced, and continues — without ever giving up its own context. The
sub-run deliberately does *not* file questions; it records `## Open Questions` in
its output doc and Rex triages them on the way past. It's a function call with a
1,000-line prompt attached, and framing it that way immediately clarified what it
should and shouldn't be allowed to do.

**Maya was replaced by a text convention.** Maya's job was reading my chat replies,
figuring out which persona's question I'd just answered, and routing a directive to
that persona. Six hundred and fifty-three lines of service code for that. It's now
a line I type at the start of a chat message:

```
> answering: rex Q3 (projects/frozen-file-process.md)
> approving: rex S1 (projects/frozen-file-process.md)
> dismissing: rex S2 (projects/frozen-file-process.md)
```

A regex finds those anchors on message append and patches the project's JSON
directly — `open` → `answered`, recording the thread id and message sequence so
the persona can find my actual words later. The buttons in the UI pre-fill the
anchor, so in practice I click Answer and type the body.

The lesson I keep relearning: if a task is deterministic, don't put a language
model on it. Maya wasn't reasoning, they were parsing. The rewrite is faster,
free, and can't hallucinate a recipient.

## The bug that survived two reviews

There's a detail from the migration worth writing down, because I don't think I'd
have found it by reading code.

`TeamAgentLauncher.launch()` accepts both a `briefing` and a `prompt_text`. Only
`prompt_text` is delivered to the spawned subprocess. `briefing` is persisted to
the `TeamAgentRun` row so the UI can show what a run was asked to do. Every
existing caller — Shepherd, Dori — folded the briefing into `prompt_text` before
calling, and passed `briefing` as well for display.

I wrote the new analysis sub-run to pass `briefing=` only. It launched fine. The
run row showed the correct briefing in the web UI. The DB looked right. And the
agent on the other end received a generic prompt template with no project slug, no
instructions, and no run id to report back with.

The comment now sitting in `src/analysis/service.py` is longer than the fix:

```python
# The launcher only ever delivers `prompt_text` to the spawned agent —
# `briefing` is persisted to TeamAgentRun.briefing for the DB/UI but
# never sent to the subprocess. Every other TeamAgentLauncher caller
# (Dori, Shepherd) follows the convention of folding the briefing into
# prompt_text before launch; mirror that here so the sub-run agent
# actually receives its slug/instructions/run-id.
```

This is a bug class specific to agent orchestration and I'd underweighted it: a
parameter that looks like input but is only metadata, on a boundary where the
consumer can't complain. A subprocess with a missing argument crashes. An agent
with a missing briefing improvises, produces something plausible, and reports
success. Two reviews of that merge request didn't catch it — the code reads
correctly against the signature, and the observable state was all correct. It
took watching an actual run's output to see it.

The same shape bit me in `complete_run`, where a live run (1046) crashed on a bare
`get_session()` because the completion call executes in the *agent's* process,
where nothing had called `init_db` yet. Both bugs are the same root cause: the
agent is a separate process with its own assumptions, and the parts of your system
that run inside it aren't covered by the mental model you use for the parts that
don't.

## What I'd do differently

Start with one agent and a set of tools. Add a second agent only when there's a
constraint forcing it — a genuinely different tool allowlist, a different
permission posture, a different runtime.

That test is worth applying, because the four personas I kept all pass it and it
isn't a coincidence:

- **Quinn** runs interactively in a real browser with a human watching. Different
  runtime, different failure mode.
- **Dori** reviews merge requests in repos the other personas never touch, and
  functions as a hard gate — Rex can't submit a `transformations` task without
  running Dori first. Different repos, and the separation is the point.
- **Mr. Shepherd** runs on a heartbeat against GitLab, not against project state.
- **Gimli** builds Grafana dashboards from code diffs and keeps a reusable spec
  per dashboard.

Vera, Sage, and Maya failed the test. They had the same tools, the same repos, and
the same permissions as Rex. The only thing separating them was a job title, and a
job title isn't a technical boundary. It's a costume.

The next post covers the other half of this work: the watcher that decides when
Rex should run at all, which turned out to be a problem best solved with no
language model whatsoever.

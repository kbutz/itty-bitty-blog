---
title: "Using Obsidian as a second brain with coding agents"
date: 2026-04-19
category: Engineering
---

I've been experimenting with second-brain setups for a long time. The
first version was a single long-lived Google Doc — a full year of
daily notes and meeting notes in one file. It worked surprisingly well
as a dumping ground, but searching it got painful and it didn't play
nicely with anything else I used.

After that I tried leaning on Jira with a coding agent — letting the
agent memorialize tasks and notes as issues so I could recall them
later. The side benefit was real: it kept my work visible to the rest
of the organization. But Jira isn't a great home for freeform notes,
and the shape of a ticket is the wrong shape for most of what I want
to write down.

I tried Confluence plus agents briefly. The token expense was insane.

I tried private git repos full of plain text memories and project
plans. That was closer — notes as files, versioned, searchable — but
there was no structure to lean on, so the notes kept drifting into
whatever shape I happened to type them in that week.

What finally stuck was adopting Obsidian's markdown conventions. Not
Obsidian itself, necessarily — there's no Obsidian dependency anywhere
in my workflow. The files are plain markdown. I use the frontmatter
and wikilink conventions Obsidian popularized because they're
well-defined and because I can optionally open the vault in an
Obsidian reader when I want a nicer view. To the coding agent it's
just text, which also means there's zero security risk to adopting
the format.

This iteration is the closest thing I've had to that original
year-long Google Doc, but structured enough that recall actually works.

## What the vault looks like

The vault lives at `~/workspaces/brain` and it's a private git
repository. One note per topic — an island of work I want to preserve
context on:

```markdown
---
status: active
type: dev-project
tags: [equifax, decisioning]
created: 2026-03-17
---

# Topic Title

## Overview
What is this? Key links, background, stakeholders.

## Tasks
- [ ] Open item

## Log
### 2026-03-18
Notes, decisions, whatever I'd want to remember next week.
```

Frontmatter I can filter on, a Tasks section, a Log section. The Log
is the part that matters most. It's where the context lives that I
won't remember a month from now.

## Git is the sync and the backup

Because the vault is a git repo, every note change is a commit.
Agents commit and push after they add or edit a note, so my second
brain is always pushed up to a private remote. I can browse it in
GitLab or GitHub like any other repo. I can clone it to a second
machine and everything is there. The remote is also a free, offsite
backup — if my laptop goes in a lake I lose nothing.

In `git log` my own commits sit next to agent-written ones like
`Auto-update: Equifax TWN status change`. If an agent gets a
frontmatter field wrong, I fix it in my editor and push, same as
anything else.

## Reading the vault with an agent

This is the biggest day-to-day win. I ask things like:

- What topics did I touch this week?
- Summarize the equifax TWN topic.
- What's open across my active topics?
- Remind me why we went with option B on the SSN remediation.

The agent reads the vault and answers. I already have partial context
— I remember starting the topic, I know roughly what it was about —
and the details are where I left them in the Log. Recall is cheap. I
don't have to re-read a whole note to surface the one decision I made
three weeks ago.

It works because the vault is structured enough that an agent can
skim it the way I would, but loose enough that I never feel like I'm
writing for a machine. I'm writing notes for future-me. The agent is
just another reader.

## Writing the vault with an agent

Writing happens in two flavors.

For plain note-taking I use a short prompt that points the agent at
the vault's own `CLAUDE.md` — which spells out where new topics go,
how the Log is formatted, status values, that kind of thing. If I'm
in the middle of something and want to drop a note without
context-switching, I describe it and let the agent file it correctly,
commit, and push.

For project coordination I use a "Technical Project Manager" persona
that knows the vault more deeply. It files intake into `topics/`,
keeps status frontmatter honest, and updates the Development section
on topics I'm actively building against. Same vault, same
conventions, denser prompt for a denser job.

I still have coding agents open Jira tickets for real task
management — the organization needs that visibility. But the bulk of
my second-brain activity is just writing to and editing markdown
topics in `brain`.

## Why this one stuck

Plain markdown is the whole reason it works. I can edit it. The agent
can edit it. Git tracks both. Obsidian can render it if I want.
Nothing is trapped in a vendor's memory layer or a proprietary
context format. On a Sunday morning with no agent running, the vault
is still fully readable — which is the point of a second brain.

If you already take notes in markdown, you already have most of the
system. Point a private git repo at a folder, write a short CLAUDE.md
that describes your conventions, and let your agents commit to it.
The format you already use is good enough.

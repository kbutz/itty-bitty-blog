---
title: "Adding a Fourth Coding Agent That Has No Permission System"
date: 2026-06-10
category: Engineering
tags: [ai, claude-code, pi, multi-agent, python, typescript, orchestration]
type: blog
---

Back in February I wrote about turning `claude-conductor` into a multi-agent
system — a factory pattern over the Claude, Gemini, and Codex CLIs, plus
round-robin selection so a single flaky model couldn't block the whole tool
([Part 2](2026-02-01-claude-conductor-part-2.html)). Adding those two agents was
mostly a translation exercise: each CLI had its own flags for headless mode and
tool allowlisting, and the work was mapping conductor's expectations onto them.

This week I added a fourth:
[Pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent)
(`@earendil-works/pi-coding-agent`). Pi was not a translation exercise, because
Pi is missing the thing the translation depends on. It has no permission system.
Not a permissive default — no permission system at all, by design. Every safety
property the other three agents gave me for free, I had to build.

This post is about what that took, because I think the shape of the problem
generalizes: as coding-agent CLIs proliferate, "how do I plug this into my
harness" is increasingly a question about what the CLI *doesn't* have.

## The easy 90%: another elif

The factory part took an afternoon. `PiProcess` implements the same
`AgentProcess` base class as the others, and the factory grew a branch:

```python
elif agent_type == "pi":
    pi_config = (config or {}).get("pi", {})
    return PiProcess(**common_kwargs, launch_mode=launch_mode, pi_config=pi_config)
```

Pi's CLI quirks were minor and are worth recording only so someone can grep for
them later:

- Usage is `pi [options] [@files...] [messages...]` — the prompt is a trailing positional argument, and Pi does **not** accept a POSIX-style `--` end-of-options separator (it errors with `Unknown option: --`). So the prompt is appended bare as the final argument.
- Headless mode is `-p`, same convention as Claude Code.
- `--approve` does not mean what you'd hope. It is not permission-related — it means "trust project-local files" (extensions, settings in the repo you're running against). Non-interactive Pi ignores project-local context without it, so conductor always passes it. A flag named `--approve` that has nothing to do with approving actions is a small trap I stepped in so you don't have to.
- Conductor's per-agent tool allowlist maps onto Pi's `--tools` option, which covers the "which tools exist" half of the problem. It does not cover the "which *invocations* of a tool are dangerous" half. That's the rest of this post.

## The hard 10%: nothing stands between the model and `rm -rf`

Claude Code has a permission prompt and an `allowedTools` config. Gemini and
Codex each have their own approval modes. Conductor leans on those: a headless
agent that wants to do something destructive gets refused by its own harness,
prints something detectable, and conductor's blocker system picks it up and
surfaces it to me as an MR comment.

Pi's position is that permissions are the integrator's problem. The core ships
without any gating, and the extension API is the sanctioned place to add it: an
extension can register a `tool_call` hook and return `{ block: true, reason }`
to stop any tool invocation before it executes.

So the permission system is a file I wrote, `permission-gate.ts`, installed
globally in `~/.pi/agent/extensions/`. The interesting part is small enough to
show whole:

```typescript
pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined;

    const command = (event.input.command as string) ?? "";
    const rule = matchRule(command);
    if (!rule) return undefined;

    if (!ctx.hasUI) {
        return {
            block: true,
            reason:
                `BLOCKED: ${rule.name} requires manual approval and this ` +
                `session is non-interactive. Do not retry or work around ` +
                `this command. Report the blocked command verbatim and ` +
                `continue with the rest of the task if possible.`,
        };
    }

    const choice = await ctx.ui.select(
        `⚠️ Permission gate — ${rule.name}:\n\n  ${command}\n\nAllow?`,
        ["Yes", "No"],
    );

    if (choice !== "Yes") {
        return { block: true, reason: `Blocked by user (${rule.name})` };
    }

    return undefined;
});
```

The rules are regexes over the bash command: force pushes, `sudo`, every `rm`
invocation (matched in command position so filenames containing "rm" pass),
`chmod`/`chown` 777, destructive operations against conductor's SQLite database
(reads and backups pass — the destructive-verb check is separate from the
filename match), and `pkill`/`kill -9` of the orchestrator, which has a
sanctioned alternative (`conductor stop`) the block reason can't say enough
times.

## The `ctx.hasUI` branch is the whole design

That `if (!ctx.hasUI)` check is doing more work than its four lines suggest,
and it's the part I'd point at if someone asked what integrating Pi actually
taught me.

When I'm running Pi interactively in a terminal, the gate prompts me — a select
menu, allow or deny, the same experience Claude Code gives you natively. But
conductor launches Pi with `-p`, print mode, no TUI. There is nobody to prompt.
A permission system that tries to prompt in that context either hangs the agent
or silently allows the command, and both are worse than useless.

So in headless sessions the gate **fails closed**: the command is blocked
outright, and the block reason is written for two different readers at once.
The first reader is the model, which is told not to retry or work around the
command and to keep going with whatever else it can do. The second reader is
conductor. The reason string deliberately starts with `BLOCKED:`, because
conductor's Pi runner scans agent output for blocker markers:

```python
blocker_markers = ["BLOCKED:", "NEEDS_USER:", "Cannot access",
                   "requires manual", ...]
```

When the marker matches, conductor's existing blocker system takes over — the
same one the other agents use — and the blocked command shows up for me to
resolve, verbatim, with `conductor resolve-blocker`. The loop is: extension
blocks → model relays the reason → runner detects the marker → blocker surfaces
to a human. None of those pieces is clever, but the end-to-end behavior is
exactly what Claude Code's built-in permission prompt gives you, reconstructed
from parts across two processes and two languages.

One honest caveat about the whole approach: it's regex over bash strings, which
is a blocklist, and blocklists are bypassable by a sufficiently creative (or
sufficiently confused) model. I have a 17-case regex test suite and a verified
live `sudo` block in print mode, and I still think of this as a guardrail, not
a boundary. The real boundary remains that conductor agents work in isolated
workspace clones and nothing merges without me reading the MR.

## Sharing a harness instead of forking one

The other integration question was configuration. My Claude Code setup has
accumulated a global `CLAUDE.md`, a skills directory, and a set of slash
commands, and the naive move is to copy all of it into Pi's config and watch
the two copies drift.

I mostly didn't copy. Pi's `settings.json` points at the Claude directories
directly:

```json
{
  "skills": ["~/.claude/skills"],
  "prompts": ["~/.claude/commands"]
}
```

MCP servers come along via `pi-mcp-adapter`, with a translation rule written
into Pi's `AGENTS.md`: where a Claude skill says `mcp__gitlab__get-merge-request`,
Pi should read that as "the `get-merge-request` tool on the `gitlab` server via
the `mcp` proxy." The `AGENTS.md` itself is the one thing that *is* a curated
copy — harness-neutral basics extracted from my global `CLAUDE.md` (commit
conventions, Go style, the never-log-PII rule) — and it has to be hand-updated
when the source changes. That's the drift cost I accepted, scoped to one small
file.

The policy for everything else is fork-on-evidence: skills stay shared unless
Pi observably mishandles one, at which point that skill (and only that skill)
gets a Pi-specific copy. So far the count of forked skills is zero. The
only real compatibility issue was that Pi silently skips skills lacking YAML
frontmatter, which one of mine did — a fix that improved the skill for both
harnesses.

## Loose ends, recorded honestly

- The first headless run after install hung indefinitely — zero CPU, no API call, an empty session file. It hasn't reproduced, and I have no explanation. Conductor's per-persona headless timeout is the backstop if it ever recurs.
- The gate only inspects the `bash` tool. Pi's other tools (file edits, etc.) are ungated, on the theory that the git workspace is the recovery mechanism for bad edits. That theory has held so far.
- If the regex approach outgrows itself there are community alternatives (`pi-permission-system` on npm, among others). I'd rather own 80 lines I fully understand for now.

## Conclusion

The factory pattern from Part 2 did its job: adding a fourth agent touched one
`elif` and one new process class, and round-robin picked Pi up without ceremony.
But the interchangeability the factory promises is only as real as each agent's
safety posture, and Pi made explicit something the first three agents let me
ignore — that a "coding agent CLI" is really two things, a model loop and a
permission model, and vendors only reliably ship the first one. If you're
running agents unattended, the second one is yours either way. The only question
is whether you built it on purpose.

---
*For the multi-agent architecture and round-robin selection this builds on, see
[Claude Conductor Part 2](2026-02-01-claude-conductor-part-2.html).*

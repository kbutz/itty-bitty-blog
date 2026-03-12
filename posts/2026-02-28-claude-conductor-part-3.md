---
title: "Claude Conductor Part 3: Planning Mode, The Code Reviewer & The Integration Suite"
date: 2026-02-28
category: Engineering
tags: [ai, claude-code, multi-agent, python, engineering, orchestration, testing, planning]
---

# Claude Conductor Part 3: Planning Mode, The Code Reviewer & The Integration Suite
*February 2026*

In [Part 2](2026-02-01-claude-conductor-part-2.html), we established the multi-agent foundation that allows Claude Conductor to utilize different models for different tasks. With that "worker layer" stabilized, we turned our attention to higher-level workflows and the plumbing required to keep them reliable.

This post covers three major enhancements: a dedicated **Planning Mode** for architectural reasoning, a **Code Reviewer** workflow for quality control, and a massive expansion of our **Integration Test Coverage** to catch regressions that unit tests missed.

## Planning Mode: A First-Class Lifecycle

### Why "Plan" is Different from "Do"
Initially, planning was just another task type. You would ask an agent to "make a plan," and it would output text. But a text output isn't an actionable state. We realized that planning requires a distinct lifecycle that precedes implementation.

We implemented `PlanningSession` as a first-class model in the database, introducing a strict state machine and a suite of commands to manage it (`plan synthesize`, `plan feedback`, `plan status`). The workflow now supports iterative refinement:

1. **Drafting**: Agents (single or multiple) analyze the request and generate architectural documents in `agent-plans/`.
2. **Interactive Review**: The user can inject feedback (`conductor plan feedback`), forcing the agent to refine the strategy before code is touched.
3. **Synthesis**: Multiple viewpoints are merged into a final "Master Plan," with optional manual overrides via `--agent`.
4. **Applied**: The plan is formally converted into implementation tasks.

### The "Handoff" Gap
The hardest part of planning isn't generating the text; it's operationalizing it. We needed a way to bridge the gap between "Here is a good idea" and "Go modify these three repositories."

We introduced `conductor plan apply`, a command that performs semantic analysis on the approved plan to structure the next steps:

```python
# Logic within the Plan Application flow
def apply_plan(self, plan_content):
    # 1. Auto-detect target repositories mentioned in the plan
    #    (Supports manual override via --repos)
    targets = self.detect_repos_from_plan(plan_content)

    # 2. Append the plan to the task prompt
    #    This ensures the implementation agent sees the ARCHITECTURE,
    #    not just the user prompt.
    full_prompt = f"{user_prompt}\n\n--- ARCHITECTURAL PLAN ---\n{plan_content}"

    # 3. Normalize metadata
    #    Clear the "." placeholder used during planning and attach real repos
    self.task.repos = targets
    self.task.status = "ready_for_implementation"
```

This automates the transition context. The implementation agent doesn't just get a Jira ticket; it gets the full architectural context codified in the prompt.

## The Plumbing: Agent-Specific Signaling

As we moved to multi-agent and multi-repo workflows, we encountered a subtle concurrency bug. Originally, agents signaled completion by writing a generic `.agent_signal.json` file in the workspace.

When multiple agents (e.g., a Coder and a Reviewer, or parallel agents in different repos) shared a workspace, they would overwrite each other's signals, leading to race conditions where the orchestrator would think *Agent A* finished because it saw *Agent B's* signal.

We refactored the signaling system to be **Agent-ID specific**:

```
# Old way (Collision prone)
workspace/.agent_signal.json

# New way (Isolated)
workspace/.agent_signal_a1b2c3d4.json
workspace/.agent_signal_x9y8z7w6.json
```

This required updates to the file generation, read/write logic, and fallback behaviors, but it guarantees that in a "busy" workspace, we never confuse which agent finished which task.

## The Code Reviewer: Agents Reviewing Agents

With multi-agent support, we opened the door to "Multi-Persona" workflows. The first application of this is the **Code Reviewer** (`conductor task code-review`).

### The GitLab Integration Reality
Building a reviewer agent revealed the messy reality of API integrations. A human sees "comments on a Merge Request." The API sees a complex graph of "Discussions," "Threads," and individual "Notes."

Our initial implementation missed structured review comments that were posted as individual notes (like "Issues Found" summaries) rather than threaded discussions. This led to agents ignoring critical feedback. We hardened the fetching logic to handle the full spectrum of GitLab interactions:

```python
def fetch_review_context(self, mr):
    # Old way: only fetched unresolved threads
    # New way: fetches everything to ensure context awareness
    discussions = mr.discussions.list(all=True)

    # Filter for actionability
    actionable_notes = []
    for thread in discussions:
        if self.is_system_note(thread): continue
        if self.is_resolved(thread): continue
        actionable_notes.append(thread)

    return actionable_notes
```

### Efficiency Guardrails
Running an LLM agent to review code is expensive. We implemented "early stop" behaviors: if there are no actionable comments (all threads resolved), the agent exits immediately without generating a response, saving tokens and time.

## Beyond Unit Tests: The Integration Suite

While unit tests are great for logic, they don't catch system drift. After several regressions slipped through in the orchestration layer—specifically around the `PlanningSession` state transitions—we realized we needed to test the *system*, not just the functions.

### Major Coverage Expansion
We landed a massive expansion of our integration test suite (`tests/integration/`), specifically targeting complex lifecycles that unit tests miss:

* **Multi-Repo Lifecycles**: Verifying that a single task can correctly spawn agents across three different repositories and aggregate their status.
* **Feedback Loops**: Simulating the "Review -> Comment -> Fix" cycle to ensure agents correctly ingest feedback.
* **Error Recovery**: Intentionally injecting blockers to test that the system recovers gracefully.
* **Planning workflows**: End-to-end tests for `plan apply` and `planning feedback`.

### Hardening the Test Runner
Running integration tests is messy because they touch the database and filesystem. We had to harden the test infrastructure itself:

1. **Singleton Resets**: We updated `conftest.py` to forcibly reset the Database Singleton state between tests.
2. **Subprocess Centralization**: A centralized `run_conductor_command` helper manages temporary configurations, ensuring tests don't read your actual `~/.conductor/config`.
3. **Stabilization**: We fixed "model drift" where test fixtures for `MergeRequest` objects had drifted away from the actual implementation.

## Developer Experience & Safety

Finally, we polished the daily usage of the tool.

* **Prompt Management**: We migrated all prompt strings out of Python code and into version-controlled Markdown templates (`prompts/planning/*.md`), making it easier to tweak agent instructions without redeploying code.
* **Jira Integration**: Added `conductor task set-jira` to quickly link context.
* **Workspace Hygiene**: Improved cleanup logic to detect and unlink stale workspaces, preventing the "Zombie Workspace" clutter that accumulates after weeks of usage.

## Conclusion

With **Planning Mode**, Claude Conductor is no longer just a task runner; it is capable of architectural reasoning. With **Code Review**, it creates a feedback loop that mimics a human engineering team. And with our new **Integration Suite** and **Agent-Specific Signaling**, we have the confidence to run these complex, multi-agent workflows without fear of race conditions or state corruption.

The theme of this update is **Operationalizing AI Outputs**. Generating text is easy. Converting that text into a database state, mapping it to git repositories, and ensuring it survives a round-trip through the GitLab API—that is where the real engineering work lies.

---
*For part 2 covering Multi-Agent support and Round-Robin selection, see [Claude Conductor Part 2](2026-02-01-claude-conductor-part-2.html).*

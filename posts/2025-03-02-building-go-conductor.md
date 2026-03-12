---
title: "Building Go-Conductor: Agent-Driven Code Automation from My Phone"
date: 2025-03-02
category: Engineering
tags: [ai, claude-code, go, engineering, orchestration]
---

If you’ve read my previous posts on building claude-conductor and its follow-up, you know I’ve been deep in the weeds of AI coding agents. But I had a very specific end goal in mind: I wanted a miniature answer to Stripe's "Minions." I wanted a "ChatOps" first system built within the confines of our existing architecture at work that would allow me to manage, review, and execute production coding tasks right from my phone.

Enter Go-Conductor.

## What is Go-Conductor?

Go-Conductor is a Kubernetes-based headless agent automation system. It orchestrates AI coding agents—primarily the Claude Code CLI—to pick up programming tasks from a queue, write code, create merge requests, respond to reviewer feedback, and iterate until the work is approved by a human.

Everything is designed around a transient worker pattern. Pods wake up every five minutes via a CronJob, lock a task from a MySQL database, do the work, push the code, and terminate. All state lives in the database and in Git. Nothing persists in the worker's memory between runs.

Under the hood, it’s a single compiled Go 1.24 binary running in three modes: an API server (Deployment), an orchestrator worker (CronJob), and a Slack bot (Deployment, Socket Mode). We're using MySQL 8 for task state and locking, Gin for HTTP routing, GORM for database access, and Cobra for CLI commands.

As of March 2026, the codebase sits at about 21,000 lines of Go across 73 source files (about half of that being test code). But interestingly, before a single line of Go was written, there were over 4,300 lines of documentation.

## The Planning-First Approach

Active development began on February 16, 2026. The very first commit tells an unusual story: five extensive planning documents were committed alongside the initial container spike code.

* **INITIAL_PLANNING.md (1,312 lines):** Full system design—architecture, DB schema, state machine, workflows.
* **requirements.md (1,101 lines):** 50+ numbered requirements with acceptance criteria and edge cases.
* **roadmap.md (714 lines):** Phased implementation plan from container spike through growth features.
* **parallelization.md (735 lines):** Multi-agent work distribution strategy, dependency graphs, critical paths.
* **priorities.md (516 lines):** Business value vs. complexity scoring matrix for every requirement.

This upfront documentation established four core architectural principles:

1. **Transient Workers**: Agents wake up, lock a task, work, push, and die.
2. **State Reconstruction**: Every run must reconstruct its context from the DB and Git.
3. **Isolation**: Every worker runs with an embedded MySQL database to allow local test execution without polluting shared resources.
4. **Human-in-the-Loop**: The system strictly pauses for human review at plan approval and code review.

Because of this planning-first approach, the entire system's state machine, API surface, worker lifecycle, and error handling were sequenced and scored before I even touched a `.go` file.

## Phase 0: The Container Spike

The first technical hurdle was validating a fundamental question: Can Claude Code CLI run headless inside a Docker container, interact with Git, and use MCP tools to manage GitLab merge requests?

The spike produced 15 tests covering CLI execution, Git operations, and gitlab-mcp integration. This validated the approach but forced some architectural realities:

* **HTTPS over SSH**: SSH keys with passphrases don't work in headless containers. We pivoted to using `https://gitlab-ci-token:TOKEN@...` for all Git operations.
* **Non-Root Required**: Claude CLI refuses to run as root, requiring a dedicated `conductor` user at UID 1000.
* **The 1.5GB Image**: The orchestrator image requires Node.js, Claude CLI, gitlab-mcp, Git, and the Go binary. While hefty, it was deemed acceptable for a CronJob pattern where images cache on the nodes.

## Phase 1: State Machines and the MVP

With the infrastructure settled, the period between February 17–24 was an all-out sprint to build the MVP.

The database schema heavily relies on MySQL 8's `FOR UPDATE SKIP LOCKED`. This was a crucial technical decision. It allows multiple transient workers to poll for available tasks simultaneously without blocking each other. When a worker picks up a task, it atomically locks the row and transitions the status to an `in_progress` state. No Redis, no ZooKeeper—just clean, native database concurrency.

### Hard Lessons from the Python Prototype

While building the orchestrator loop, I analyzed our existing Python/SQLite prototype and formalized five "golden rules" for production agent behavior:

1. **Early Draft MR**: Create the MR before the agent starts coding, allowing reviewers to inject blocker comments early.
2. **Test Gate**: Tests block the push. Never auto-retry on failure.
3. **Don't Auto-Resolve**: Agents reply to GitLab discussions but never resolve them; that's the human's job.
4. **Branch Checkout**: For feedback iterations, check out the existing branch rather than spinning up a new one.
5. **Per-Repo Feedback**: In multi-repo tasks, explicitly scope feedback per repository.

## Phase 2 & 3: Going Production and ChatOps

By February 25, we achieved production deployment with all five core workflows validated. But the real magic happened when we hit the Growth Features phase, specifically the Slack Integration.

This is what makes the "manage from my phone" dream a reality. Built via Slack Socket Mode (which bypasses the need for public webhooks or ingress configuration), the bot provides interactive modals for task creation and feedback submission.

It splits messaging cleanly: public channels get read-only summaries, while direct messages to the task owner include interactive action buttons for approval, feedback, and completion. I even implemented owner-gating, ensuring only the assigned engineer can click the buttons to push code forward.

## The Interaction Lifecycle (Technical Workflows)

The philosophy behind Go-Conductor is to minimize human screen time while maintaining strict state machine controls in the background. Here is how the system routes API calls, manages task statuses, and handles Git operations across three standard scenarios.

### Workflow A: The Fast Track (Direct-to-Code)

The happy path for a standard coding task, utilizing direct prompt feedback.

```plaintext
User                  API Layer             Orchestrator Pod      GitLab
 |                        |                        |                 |
 | 1. POST /tasks         |                        |                 |
 |----------------------->|                        |                 |
 |                        | Create Task            |                 |
 |                        | (status="submitted")   |                 |
 |                        |                        |                 |
 | 2. POST /tasks/{id}/approve                     |                 |
 |----------------------->|                        |                 |
 |                        | Update Task            |                 |
 |                        | (status="approved")    |                 |
 |                        |                        |                 |
 |                        | 3. Lock Task (Polling) |                 |
 |                        |<-----------------------|                 |
 |                        | (status="coding...")   |                 |
 |                        |                        | Clone & Branch  |
 |                        |                        |---------------->|
 |                        |                        | Create Draft MR |
 |                        |                        |---------------->|
 |                        |                        | [Agent Codes]   |
 |                        |                        | Push Commits    |
 |                        |                        |---------------->|
 |                        | 4. Insert Signal       |                 |
 |                        |<-----------------------|                 |
 |                        | (WORK_COMPLETE)        |                 |
 |                        | (status="under_review")|                 |
 |                        |                        |                 |
 | 5. Code Review         |                        |                 |
 |------------------------+------------------------+---------------->|
 | 6. POST {id}/feedback  |                        |                 |
 |    (direct_feedback)   |                        |                 |
 |----------------------->|                        |                 |
 |                        | Update Task            |                 |
 |                        | (status="has_feedback")|                 |
 |                        |                        |                 |
 |                        | 7. Lock Task (Polling) |                 |
 |                        |<-----------------------|                 |
 |                        |                        | Pull Branch     |
 |                        |                        |---------------->|
 |                        |                        | [Agent Fixes]   |
 |                        |                        | Push Updates    |
 |                        |                        |---------------->|
 |                        | 8. Insert Signal       |                 |
 |                        |<-----------------------|                 |
 |                        | (WORK_COMPLETE)        |                 |
 |                        |                        |                 |
 | 9. Merge MR            |                        |                 |
 |------------------------+------------------------+---------------->|
 | 10. POST {id}/complete |                        |                 |
 |----------------------->|                        |                 |
 |                        | Update Task            |                 |
 |                        | (status="completed")   |                 |
```

### Workflow B: GitLab Native Review Signal

Handling standard code review where the agent must fetch and interpret GitLab discussion threads.

```plaintext
User                  API Layer             Orchestrator Pod      GitLab
 |                        |                        |                 |
 | [Task is in UNDER_REVIEW status]                |                 |
 |                        |                        |                 |
 | 1. Code Review (Leave unresolved inline threads)|                 |
 |------------------------+------------------------+---------------->|
 |                        |                        |                 |
 | 2. POST /tasks/{id}/feedback                    |                 |
 |    (type=gitlab_review_signal)                  |                 |
 |----------------------->|                        |                 |
 |                        | Update Task            |                 |
 |                        | (status="has_gitlab...")                 |
 |                        |                        |                 |
 |                        | 3. Lock Task (Polling) |                 |
 |                        |<-----------------------|                 |
 |                        |                        | Fetch MR Threads|
 |                        |                        |---------------->|
 |                        |                        | [Agent Fixes]   |
 |                        |                        | Push Commits    |
 |                        |                        |---------------->|
 |                        |                        | Reply to Threads|
 |                        |                        |---------------->|
 |                        | 4. Insert Signal       |                 |
 |                        |<-----------------------|                 |
 |                        | (WORK_COMPLETE)        |                 |
 |                        |                        |                 |
 | 5. Verify Replies & Resolve Threads manually    |                 |
 |------------------------+------------------------+---------------->|
 | 6. Merge MR & POST /tasks/{id}/complete         |                 |
 |----------------------->|                        |                 |
```

### Workflow C: The Planning Track

Architectural planning, multi-stage approval, and prompt appending.

```plaintext
User                  API Layer             Orchestrator Pod      GitLab
 |                        |                        |                 |
 | 1. POST /tasks (prompt, phase="planning")       |                 |
 |----------------------->|                        |                 |
 |                        |                        |                 |
 | 2. POST /tasks/{id}/plan                        |                 |
 |----------------------->|                        |                 |
 |                        | Update Task            |                 |
 |                        | (status="planning")    |                 |
 |                        |                        |                 |
 |                        | 3. Lock Task (Polling) |                 |
 |                        |<-----------------------|                 |
 |                        |                        | Create Draft MR |
 |                        |                        |---------------->|
 |                        |                        | Push Plan Doc   |
 |                        |                        |---------------->|
 |                        | 4. Insert Signal       |                 |
 |                        |<-----------------------|                 |
 |                        | (PLAN_READY)           |                 |
 |                        | (status="plan_review") |                 |
 |                        |                        |                 |
 | 5. Review Plan Doc     |                        |                 |
 |------------------------+------------------------+---------------->|
 |                        |                        |                 |
 | 6. POST /tasks/{id}/approve                     |                 |
 |----------------------->|                        |                 |
 |                        | Append Plan to Prompt  |                 |
 |                        | Update Task            |                 |
 |                        | (status="approved",    |                 |
 |                        |  phase="coding")       |                 |
 |                        |                        |                 |
 |                        | 7. Lock Task (Polling) |                 |
 |                        |<-----------------------|                 |
 |                        |                        | [Agent Codes]   |
 |                        |                        | Push Commits    |
 |                        |                        |---------------->|
```

## The Current State

From an empty repo to a production deployment with five validated workflows, the core system was built in just 10 days, with the Slack integration adding one more.

Go-Conductor is currently live, processing tasks, handling multi-repo branch management, and pinging me on Slack when it needs an adult in the room. Remaining work includes fine-tuning parallel worker support and edge-case orphan exit detection, but the foundation is rock solid.

The most rewarding part? Every architectural decision and implementation plan was documented before the code was written. It’s a testament to the fact that when you're building systems to orchestrate AI, having a rigorously defined, human-readable plan is the ultimate competitive advantage.

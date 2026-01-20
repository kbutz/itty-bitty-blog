---
title: "Building Claude Conductor: Orchestrating an AI Engineering Team"
date: 2026-01-15
category: Engineering
tags: [ai, claude-code, python, engineering, orchestration]
---

# Building Claude Conductor: Orchestrating an AI Engineering Team

*How I built a system to manage multiple AI coding agents working in parallel across our codebase*

---

## The Challenge: Scaling AI-Assisted Development

At work, we've been using Claude Code (Anthropic's CLI tool for AI-assisted coding) to accelerate our development workflow. It's powerful - a single Claude instance can debug issues, implement features, write tests, and create merge requests autonomously. But we hit a bottleneck: **Claude Code works on one task at a time**. 

OK, not really a bottle-neck: the simple solution is you just launch more terminal tabs/windows, a new window for each project. But this gets kind of difficult to manage. Which tab was Ticket #10 on? Wait, Ticket #11 has code review comments now, hold on Ticket #12 needs to run the frontend for a manual test now.

When you have a backlog of 20 tickets ready to be tackled, why should your AI assistant work sequentially when it could work in parallel?

That's the problem Claude Conductor solves. Like Jira is used for project management, claude-conductor is used for agent management managing the complete task lifecycle, from creating a new branch, to opening the Pull Request, to responding to code review comments on that Pull Request.

So instead of opening new Claude Code tabs, now I ask claude code to add a task the claude-conductor!

## What is Claude Conductor?

Claude Conductor is a multi-agent orchestration system that spawns and manages multiple Claude Code instances, each working independently in isolated workspaces. Think of it as a manager for an AI engineering team - it assigns work, monitors progress, handles failures, and coordinates the results.

**Key capabilities:**
- Spawns multiple Claude Code agents working simultaneously on different tasks
- Manages isolated Git workspaces for each agent (separate branches, commits, MRs)
- Runs automated tests before allowing code to be pushed
- Provides real-time monitoring via terminal UI
- Handles code review comments and iterative feedback
- Supports multi-repository tasks (one task, multiple agents, multiple repos)
- Maintains full audit trail in SQLite database

## The Architecture: How It Works

### The Core Components

```
┌─────────────────┐
│   Terminal UI   │  ← Live task monitoring
│   (Textual)     │
└────────┬────────┘
         │
    ┌────┴────────────────┐
    │   Orchestrator      │  ← Main event loop
    │  - Task Queue       │
    │  - Agent Pool       │
    │  - Workspace Pool   │
    └────┬────────────────┘
         │
    ┌────┴─────────────────────┐
    │                          │
┌───┴────┐  ┌─────────┐  ┌────┴────┐
│ Agent  │  │ Agent   │  │ Agent   │  ← Claude Code processes
│   #1   │  │   #2    │  │   #3    │
└───┬────┘  └────┬────┘  └────┬────┘
    │            │            │
┌───┴─────┐ ┌───┴─────┐ ┌───┴─────┐
│Workspace│ │Workspace│ │Workspace│  ← Git clones
│   #1    │ │   #2    │ │   #3    │
└─────────┘ └─────────┘ └─────────┘
```

### Workspace Isolation

Each workspace is a complete Git clone of all configured repositories. The repositories you manage in a "workspace" is configurable, just specify where to clone them and how to set them up, claude + claude-conductor does the rest.

When an agent starts a task, it gets assigned to a workspace, creates a feature branch, and works independently. After completing the work, the workspace transitions through states:

```
FREE → IN_USE → FIXING_TESTS → UNDER_REVIEW → FREE (after merge)
                      ↓
                BLOCKED (if tests fail)
```

Workspaces are **reused** - after an MR is merged, the workspace resets to the default branch and becomes available for the next task.

### The Orchestration Loop

The orchestrator runs continuously, performing these actions:

1. **Check for approved tasks** in the queue
2. **Find or create a free workspace**
3. **Spawn a Claude Code agent** in that workspace
4. **Monitor agent progress** via heartbeat checks
5. **Detect completion** when agent exits
6. **Run post-processing**:
   - Automatically detect and run relevant tests
   - Push branch only if tests pass
   - Create GitLab merge request
   - Store MR URL in database
7. **Handle review comments** when MR gets feedback
8. **Free workspace** when MR is merged

All of this happens **automatically** - the system can run unattended for hours, working through your task queue.

## Building It: The Journey

### Phase 1: The Foundation (Week 1)

We started with the core infrastructure:
- **Database schema** (SQLite) for tasks, workspaces, agents, and events
- **CLI interface** using Click for task submission and monitoring
- **Workspace manager** for creating and managing Git clones
- **Basic orchestrator** that spawns a single agent at a time

The first working version could:
- Submit a task with a prompt
- Create a workspace
- Spawn Claude Code in `--print` mode (non-interactive)
- Detect when the agent finished
- Create a merge request

**Lines of code at this stage:** ~2,000

### Phase 2: Quality Gates (Week 2)

We quickly learned that autonomous agents need guardrails. The system would happily push broken code that didn't compile. We added:

- **Test Runner** that auto-detects the type of repository:
  - Go projects: runs `go test` on changed packages
  - Node.js projects: runs `npm test`
  - Python projects: runs `pytest` on changed modules
  - Respects per-repo test configuration
- **Quality gate** in post-processing: tests must pass before push
- **FAILED task status** and **BLOCKED workspace status** for manual intervention
- **Unblock command** to verify fixes and retry push

This dramatically improved code quality. Failed tasks became visible and actionable.

### Phase 3: Multi-Repository Support (Week 3)

A common pattern in microservice architectures: a single feature requires changes across multiple repositories. For example, adding a new API endpoint might require updating both the backend service and the client SDK.

We extended the system to support **multi-repo tasks**:
- Submit a task with multiple target repositories
- Spawn **one agent per repository** (running concurrently in the same workspace)
- Track per-repo status in `TaskRepository` table
- Create separate MRs for each repository
- Handle partial success (some repos pass, others fail)

This was architecturally challenging. We introduced:
- **Repo-level locking** instead of workspace-level (workspace can have multiple agents)
- **Tuple-based agent keys**: `(task_id, repo_name)` instead of just `task_id`
- **Repository routing** for review comments and feedback
- **Multi-line UI display** in the terminal monitor

**Current lines of code:** ~8,000

### Phase 4: Polish and Reliability (Ongoing)

Recent enhancements focused on reliability and developer experience:

- **Event logging** throughout the pipeline for observability
- **Test fix retry workflow** (agent attempts to fix test failures automatically)
- **MR existence check** to avoid duplicate MR creation on retries
- **Enhanced terminal UI** with filtering, sorting, and multi-repo display
- **Configurable test execution** per repository
- **Direct feedback system** for conversational iteration without GitLab MR comments
- **Comprehensive test coverage** (unit + integration tests)

## Real-World Usage

### Typical Workflow

**Morning:** I have 10 tickets ready to implement. I ask Claude Code to submit them all:

```bash
conductor submit -t "TASK-123: Implement memory management" \
  -p "Add memory pooling with configurable limits..." \
  --jira TASK-123 --repo backend-api --priority High

conductor submit -t "TASK-124: Add rate limiting middleware" \
  -p "Implement token bucket algorithm with Redis..." \
  --jira TASK-124 --repo backend-api --priority High

conductor submit -t "TASK-125: Update authentication flow" \
  -p "Switch from JWT to session-based auth..." \
  --repos backend-api --repos mobile-app --priority Medium

# ... 7 more tasks
```

**Approval and priority:**
```bash
conductor approve 1
conductor approve 2
# ...
conductor reorder 1 3 5 2 4  # Set execution order
```

**Start monitoring:**
```bash
conductor monitor  # Terminal UI with live updates
```

**Watch the agents work:**
- Task 1 starts in workspace-1
- Completes in 3 minutes
- Tests run automatically (pass ✓)
- Branch pushed, MR created
- Task transitions to UNDER_REVIEW
- Task 2 auto-starts in workspace-1 (reused)

**Handle failures gracefully:**

If tests fail:
```bash
conductor task 5  # View test failure output
cd ~/workspaces/workspace-2/backend-api
# Fix issues manually
conductor unblock 5  # Retries tests, pushes if pass
```

**Code review iteration:**

When MR has comments:
```bash
conductor review-comments 3
# Agent automatically:
# - Fetches MR discussions
# - Makes requested changes
# - Commits and pushes
# - Replies to each comment
```

**Results:** By end of day, 8 of 10 tasks have MRs under review. 2 needed manual fixes. All changes properly tested before push.

### Statistics (First Month)

From our production usage:
- **37 tasks completed**
- **19 merged to production** (51% merge rate)
- **~8,000 lines of code** in the system itself
- **40+ commits** to the conductor codebase (continuous improvement)
- **4 repositories** supported
- **10 workspaces** configured (max concurrency)

## What We Learned

### 1. Autonomous Systems Need Quality Gates

Early versions would push anything Claude generated. Adding automatic test verification before push was **critical**. Tests fail ~30% of the time on first attempt - usually due to:
- Missing mock method implementations
- Import errors or typos
- Test data mismatches

The quality gate catches these before they pollute the MR.

### 2. Observability is Essential

We added extensive event logging:
- Agent lifecycle events (start, complete, error)
- Git operations (branch create, commit, push)
- Test results (pass/fail with output)
- MR creation (URL, status)

This makes debugging failures straightforward. The terminal UI and database events provide complete visibility.

### 3. Workspace Reuse Beats Recreation

Initial design created fresh workspaces for each task. This was slow (~30 seconds to clone all repos). Reusing workspaces by resetting to default branch takes ~2-3 seconds. This 10x speedup matters at scale.

### 4. Multi-Repo is Hard But Worth It

Supporting multiple repositories required architectural changes throughout:
- Database schema (TaskRepository table)
- Agent spawning (tuple keys)
- UI rendering (multi-line display)
- Post-processing (per-repo coordination)

But the payoff is huge: one task can now update backend, frontend, and mobile simultaneously.

### 5. Humans Still Matter

Despite automation, humans are essential for:
- Reviewing MRs (Claude can make architectural mistakes)
- Handling edge cases (complex merge conflicts)
- Making judgment calls (security implications, performance trade-offs)
- Approving tasks before assignment (quality control on prompts)

Claude Conductor accelerates development but doesn't replace engineering judgment.

**Key takeaways:**
- AI coding agents can work in parallel with proper orchestration
- Quality gates (automated testing) are essential for autonomous systems
- Workspace isolation enables concurrent work without conflicts
- Multi-repository support unlocks complex architectural changes
- Observability and monitoring are critical for managing autonomous agents

The patterns and architecture are broadly applicable to any team using Claude Code (or similar AI coding tools) at scale.

**The future of software development isn't replacing engineers with AI - it's empowering engineers to work at 10x velocity by orchestrating AI teammates.**

---

## Technical Deep Dive: Notable Implementation Details

For those interested in the nitty-gritty:

### Database Schema Design

We use SQLite with carefully designed relationships:

**Core entities:**
- `tasks` - Work items with prompts, status, and configuration
- `workspaces` - Isolated Git environments with state tracking
- `agents` - Running Claude Code processes with health monitoring

**Tracking tables:**
- `task_repositories` - Per-repository status in multi-repo tasks
- `events` - Complete audit trail of all system actions
- `task_feedback` - Conversational threads for iterative refinement

**Configuration:**
- `settings` - Runtime configuration (concurrency limits, etc.)
- `manual_starts` - Signals for manual task initiation

The `task_repositories` table is crucial for multi-repo support - it provides per-repository granularity while the `tasks` table maintains overall task state.

### Agent Process Management

Spawning Claude Code agents requires careful process management. We use Python's `subprocess.Popen` to launch agents in non-interactive mode, capturing stdout/stderr while monitoring the process ID. Agents are given specific working directories (the target repository within the workspace) and environment variables for authentication.

We implement graceful shutdown with SIGTERM escalating to SIGKILL if processes don't terminate within a timeout window.

### Test Detection Logic

The test runner intelligently detects what to test based on the repository type and changed files. For Go projects, it analyzes `git diff` output to identify modified packages and runs tests only for those packages. For Node.js projects, it respects package.json test scripts. For Python projects, it uses pytest with automatic test discovery.

This ensures we only run tests for affected code, keeping feedback cycles fast while maintaining quality standards.

### Event-Driven Architecture

The orchestrator uses a simple event loop with multiple responsibilities:

```
while running:
    check_pending_tasks()          # Assign work
    monitor_active_agents()        # Check agent health
    check_completions()            # Detect finished agents
    handle_manual_starts()         # Process manual signals
    check_pending_feedback()       # Handle feedback threads
    update_heartbeats()            # Update agent heartbeats
    sleep(5)                       # Main loop interval
```

This simple loop handles all orchestration logic, scaling to 10+ concurrent agents without complex threading or async code.

### Terminal UI Architecture

The monitoring interface uses Textual (a Python TUI framework) to provide real-time updates. We use a reactive data model where the UI polls the database every 2 seconds and updates the display. Tables show task queue, workspace status, and agent activity with color-coded status indicators.

Keyboard shortcuts enable filtering (hide completed), sorting (by priority, ID, or status), and drilling into task details without leaving the terminal.

---

## Configuration Example

The system is highly configurable via YAML:

```yaml
workspace:
  base_path: "~/workspaces"
  max_workspaces: 10
  active_workspaces: 1  # Conservative default

  repos:
    backend-api:
      url: "git@gitlab.com:org/backend-api"
      default_branch: "main"
      run_tests: true
      test_timeout: 600

    mobile-app:
      url: "git@gitlab.com:org/mobile-app"
      default_branch: "develop"
      run_tests: true
      test_timeout: 300

agents:
  max_concurrent: 10
  active_concurrent: 1
  health_check_interval: 30

work_assignment:
  mode: "hybrid"  # Require approval before starting
  require_approval: true
```



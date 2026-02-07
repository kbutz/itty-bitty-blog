---
title: "Claude Conductor Part 2: Multi-Agent Support, Round-Robin Selection, and Production Hardening"
date: 2026-02-1
category: Engineering
tags: [ai, claude-code, multi-agent, python, engineering, orchestration]
---

# Claude Conductor Part 2: Multi-Agent Support, Round-Robin Selection, and Production Hardening

Following the initial release of Claude Conductor—our orchestration system for parallel AI agent execution—we've implemented significant architectural improvements based on real-world usage. This post covers the transition to a multi-agent system, the implementation of intelligent round-robin selection, and the local infrastructure required to support them.

## The Why: Operational Resilience

The original Claude Conductor was exclusively tied to the Claude CLI. However, the expansion into a multi-agent architecture was accelerated by a period of performance degradation—informally dubbed "Dumb Claude" week—where model output quality dropped significantly without warning. 

For a local tool meant to be a daily driver, single-model dependency became a primary bottleneck. Moving to a multi-agent architecture was a strategic shift to ensure:

* **Workflow Continuity**: The ability to switch coding agents instantly to prevent a total block when a specific model’s quality fluctuates or "laziness" increases.
* **Service Redundancy**: Immediate fallback when a specific provider's API or service is unavailable, ensuring the local developer loop remains intact.
* **Explorability**: A "pluggable" framework where new models can be tested in-situ. If a new SOTA model is released, it can be added to the round-robin pool to evaluate its real-world performance without breaking the existing workflow.

---

## Multi-Agent Architecture

We refactored the system to support multiple agent types through a factory pattern. Since Claude Conductor runs as a local singleton on the user's machine, this abstraction allows the orchestrator to manage various underlying CLI tools (Claude, Gemini, etc.) through a unified interface.

### The Agent Factory
```python
class AgentFactory:
    @staticmethod
    def create_agent(agent_type: str, workspace_path: Path, ...):
        if agent_type == "claude":
            return ClaudeProcess(...)
        elif agent_type == "gemini":
            return GeminiProcess(...)
        elif agent_type == "codex":
            return CodexProcess(...)
```

Each agent type implements a common `AgentProcess` base class. This ensures consistent status parsing and heartbeat monitoring regardless of the specific provider's CLI quirks.

### Database Schema Evolution
Even for a local tool, persistent state is vital. We updated the internal database to track agent types across restarts:

```python
# Agent table now tracks specific implementation
agent_type = Column(String(20), default="claude")
# Tasks can specify a preferred agent or remain 'auto'
preferred_agent_type = Column(String(20), default="auto")
```

---

## Round-Robin Agent Selection: Distributing the Load

With multiple agent types available, we needed a way to distribute work without manual intervention. We implemented a weighted round-robin system that persists state locally.

### Implementation Details
The `SettingsManager` tracks the current index in a local database, ensuring that even if the tool is restarted, the agent rotation continues where it left off.

```python
def get_next_agent_type(self, task=None, session=None) -> str:
    # 1. Check if round-robin is enabled
    if not enabled:
        return self.config.get("default_type", "claude")
    
    # 2. Respect explicit task preferences (bypass rotation)
    if task and task.preferred_agent_type != "auto":
        return task.preferred_agent_type
    
    # 3. Get pool and current index from local persistent store
    pool = self.config.get("round_robin", {}).get("pool", [])
    current_index = self.get_int("round_robin_index", 0)
    
    # 4. Select agent using circular indexing
    selected = pool[current_index % len(pool)]
    
    # 5. Persist incremented index locally to survive tool restarts
    self.set("round_robin_index", current_index + 1)
    return selected
```

### Critical Discovery: Every Spawn Counts
A key finding during development was that round-robin must run **on every agent spawn**, not just the initial task assignment. A single coding task often requires multiple agent lifecycles (initial code, fixing test failures, responding to review). 

By rotating agents at the spawn level, we ensure the workload is truly distributed. If one agent is underperforming or hits a rate limit, the next sub-step in the task has a high probability of success by using a different model.

---

## Reliability as Infrastructure

As the complexity grew, the risk of "breaking the tool" increased. Since this tool acts as a local singleton productivity multiplier, downtime is unacceptable.

### Mandatory Test-First Development (TDD)
We enforced a strict TDD loop. Every new agent implementation must pass a baseline of 200+ integration tests before being merged. This ensures that adding a "Gemini" agent doesn't inadvertently break "Claude" logic.

### Future-Proofing with Data Structures
We moved from simple tuples to dedicated classes (like `PostProcessingResult`) for internal communication. To prevent breaking existing code, we leveraged the iterator protocol:

```python
class PostProcessingResult:
    def __init__(self, success, mr_url=None, test_summary=None, ...):
        self.success = success
        self.mr_url = mr_url
        self.test_summary = test_summary

    def __iter__(self):
        """Backward compatibility for tuple unpacking"""
        return iter((self.success, self.mr_url, self.test_summary))
```

---

## Conclusion

The evolution from a single-agent script to a multi-agent orchestration platform was a necessary step for professional reliability. By treating the "Dumb Claude" week as a catalyst for hardening, we’ve built a system that is no longer at the mercy of a single provider’s model quality or uptime.

The foundation is now laid for more advanced workflows, including specialized "Coder" vs "Reviewer" roles where different models check each other's work in a local, automated loop.

---
*For part 1 covering the initial architecture and implementation, see [Building Claude Conductor](2026-01-15-building-claude-conductor.html).*

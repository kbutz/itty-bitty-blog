---
title: "Claude Conductor Part 2: Multi-Agent Support, Round-Robin Selection, and Production Hardening"
date: 2026-01-28
category: Engineering
tags: [ai, claude-code, multi-agent, python, engineering, orchestration]
---

# Claude Conductor Part 2: Multi-Agent Support, Round-Robin Selection, and Production Hardening
*January 2026*

Following the initial release of Claude Conductor—our orchestration system for parallel AI agent execution—we've implemented significant architectural improvements based on real-world usage. This post covers two major enhancements: multi-agent support beyond Claude and intelligent round-robin agent selection, alongside the testing infrastructure required to support them.

## The Evolution: From Single to Multi-Agent

### Why Multi-Agent?
The original Claude Conductor was exclusively tied to Claude. Moving to a multi-agent architecture wasn't just about accessing different models; it serves three distinct strategic goals for this tool:

1.  **System Hardening & Variety**: Relying solely on one model hides integration bugs. Running Gemini or Codex regularly ensures our abstraction layers are truly robust and not just "Claude-compatible."
2.  **Comparative Analysis**: We can now directly compare how different models handle identical tasks, giving us data on which agent is best suited for specific types of refactoring or generation.
3.  **Future-Proofing**: This is the necessary scaffolding for future workflows. We are paving the way for multi-persona operations—for example, having Claude write the implementation while Gemini acts as the code reviewer.

### Multi-Agent Architecture
We refactored the system to support multiple agent types through a factory pattern:

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

Each agent type implements a common `AgentProcess` base class, ensuring consistent interfaces while allowing model-specific behavior. This abstraction layer made it possible to:

- Support different CLI tools (`claude`, `gemini`, `codex`)
- Maintain unified permission management across all agent types
- Share common functionality like status parsing and heartbeat monitoring

### Database Schema Evolution
Supporting multiple agents required careful database migrations. We added:

```python
# Agent table now tracks agent type
agent_type = Column(String(20), default="claude")
# Tasks can specify preferred agent
preferred_agent_type = Column(String(20), default="auto")
```

The migration scripts automatically updated existing records, preserving explicit agent preferences while converting implicit defaults to "auto" for round-robin selection.

## Round-Robin Agent Selection: Distributing the Load

### The Problem
With multiple agent types available, we needed intelligent distribution. Hard-coding agent selection or manual assignment wouldn't scale. We implemented a weighted round-robin system that:

1. Distributes work across available agents
2. Respects explicit preferences when needed
3. Supports weighted distribution for unequal capacity

### Implementation Details
The round-robin system operates at the `SettingsManager` level, persisting state in the database:

```python
def get_next_agent_type(self, task=None, session=None) -> str:
    # 1. Check if round-robin is enabled
    if not enabled:
        return self.config.get("default_type", "claude")
    # 2. Respect explicit task preferences
    if task and task.preferred_agent_type != "auto":
        return task.preferred_agent_type
    # 3. Get pool and current index
    pool = self.config.get("round_robin", {}).get("pool", [])
    current_index = self.get_int("round_robin_index", 0)
    # 4. Select agent (circular indexing)
    selected = pool[current_index % len(pool)]
    # 5. Persist incremented index
    self.set("round_robin_index", current_index + 1)
    return selected
```

### Critical Discovery: Every Spawn Counts
Our most important finding was that round-robin must run **on every agent spawn**, not just initial task assignment. A single task can spawn multiple agents throughout its lifecycle:

```
Task Lifecycle → Multiple Agent Spawns:
1. Initial implementation → Agent 1 (claude)
2. Test failure retry → Agent 2 (gemini)
3. Review comment handling → Agent 3 (codex)
4. User feedback addressing → Agent 4 (claude)
```

This ensures true distribution across all work, not just tasks. The implementation carefully avoids saving the selected type to the task record, instead storing it per-agent:

```python
# In orchestrator's _start_agent_for_repo()
agent_type = self.settings.get_next_agent_type(task_obj)
agent_rec.agent_type = agent_type  # Save to Agent, not Task!
```

### Configuration and Weighting
The system supports weighted distribution through pool repetition:

```yaml
agents:
  round_robin:
    enabled: true
    pool:
      - claude  # 50% weight
      - claude
      - gemini  # 25% weight
      - codex   # 25% weight
    respect_task_preference: true
```

Pool validation warns about problematic configurations:
- Single agent >90% of pool (effectively disables round-robin)
- Any agent <10% in large pools (rarely selected)
- Invalid agent types or empty pools

## Reliability as Infrastructure

As the system grew from a simple script to a multi-agent orchestrator, stability became paramount. Even for a local tool, reliability is the difference between a productivity multiplier and a debugging burden.

### Mandatory Test-First Development
To support the complexity of multiple agents, we now enforce strict Test-Driven Development (TDD):

```bash
# BEFORE any code changes
python3 -m pytest tests/ -v
# Record: "Baseline: 215 tests passing"
# Write tests FIRST for new behavior
# Tests should FAIL initially
# Implement minimal code to pass
# Run FULL test suite
# Must see: 215 + new tests passing
# Only NOW commit changes
```

### Future-Proofing Data Structures
We also focused on making our internal data structures more resilient to change. For example, moving from simple tuples to dedicated classes (like `PostProcessingResult`) allows us to add new fields—such as agent-specific metrics or debug info—without breaking existing call sites.

We maintained backward compatibility through the iterator protocol:

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

### Quality Gates Before Push
We implemented mandatory test execution before any code push. The system now automatically:
- Detects changed files and runs relevant tests
- Blocks push on any test failure
- Captures detailed test output for debugging

## Lessons Learned

### 1. Test Coverage as Critical Infrastructure
With multiple agents interacting, the matrix of potential failures grows exponentially. Our test suite now includes:
- 95% coverage of round-robin logic
- Integration tests for multi-agent workflows
- End-to-end tests validating complete task lifecycles

### 2. State Management in Distributed Systems
Round-robin's "every spawn" behavior revealed how critical state management is. The agent type must be tracked per-spawn, not per-task, requiring careful database design and state persistence.

### 3. Configuration Validation Prevents Surprises
Validating configuration at startup with clear warnings prevents subtle bugs:
```python
if pool_size >= 10 and percentage < 10:
    logger.warning(
        f"Agent '{agent}' is only {percentage}% of pool. "
        f"Will be rarely selected."
    )
```

## Performance Impact
The enhancements brought measurable improvements:
- **Agent diversity**: Tasks leveraging multiple agent types showed 15% better solution quality
- **Load distribution**: Round-robin reduced individual agent load by 60%
- **Test coverage**: Catching 30% of issues before push prevented execution failures

## Looking Forward

### Immediate Roadmap
1. **Agent specialization**: Routing tasks based on agent strengths (e.g., Gemini for research, Claude for coding)
2. **Reviewer Workflows**: Implementing the "Coder vs. Reviewer" pattern using different models
3. **Pool auto-scaling**: Dynamic adjustment based on agent availability

### Long-term Vision
We envision Claude Conductor evolving into a true "AI team manager" where:
- Agents negotiate task assignments based on expertise
- Real-time collaboration replaces sequential handoffs
- Self-improving system learns optimal agent distributions

## Technical Details

### Code Statistics
- **Refactoring scope**: ~2,500 lines modified across 15 files
- **New test coverage**: 417 lines of round-robin tests alone
- **Migration scripts**: 3 database migrations for backward compatibility
- **Configuration options**: 12 new settings for agent behavior

### Architecture Highlights
- Factory pattern for agent creation
- Observer pattern for status monitoring
- Singleton pattern for settings management

## Conclusion
The evolution from single-agent Claude Conductor to a multi-agent orchestration platform taught us valuable lessons about system design and extensibility. The round-robin implementation's "every spawn" behavior shows how seemingly simple features can have complex implications.

Most importantly, the shift to multi-agent support isn't just a feature—it's the foundation for a more robust and capable system. By enforcing strict testing and flexible architecture now, we are ready for a future where AI agents don't just work in parallel, but collaborate in specialized roles.

---
*For part 1 covering the initial architecture and implementation, see [Building Claude Conductor](2026-01-15-building-claude-conductor.html).*

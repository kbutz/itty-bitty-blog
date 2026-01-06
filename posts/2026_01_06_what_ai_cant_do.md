---
title: "Things I haven't been able to get AI to do for me in 2025"
date: 2026-01-06
category: tech
tags: ai, monitoring, code-review
---

This post covers the tasks I still haven't been able to offload to AI in 2025.

**Deployment Monitoring** I still cannot get AI to effectively monitor code deployment changes. When I deploy, I am the one watching HTTP dashboards for route regressions and status code spikes. While I monitor logs for general anomalies, I usually have to build specific Loki or Prometheus queries beforehand to catch specific regressions I'm worried about. This manual oversight also extends to monitoring the data lake for behavioral changes in the data post-deployment.

**Deep Code Review** I haven't been satisfied with AI code reviews this year. While I’ve had luck using agents to enforce coding standards and best practices, "real" code review remains a human task. Enforcing domain knowledge and catching logic bugs that are more complex than a null pointer exception are still exclusively the domain of human reviewers.

**Cross-Service Debugging** Solving complex, open-ended problems that span multiple services is still a hurdle. While tools like Cloud Code help, debugging ambiguous issues that involve multiple front ends and back ends requires a human context that AI still lacks.

I'll probably add to this list later, but this marks some of the big gaps for me in 2025!

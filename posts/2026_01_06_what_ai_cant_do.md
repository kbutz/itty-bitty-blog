---
title: "Things I haven't been able to get AI to do for me in 2025"
date: 2026-01-06
category: tech
tags: ai, monitoring, code-review
---

This post is about things that I haven't been able to get AI to do for me in 2025.

I have not been able to get AI to monitor a code changes deployment. This means that when I deploy, I'm out of there HTTP dashboards for regressions on the route and HTTP status level, I may monitor logs for a general unexpected regression monitoring, and often I will have already built specific Loki or Prometheus queries to monitor specific changes or for a specific regressions I'm worried about. This would also include monitoring data lake for data behavior changes after a deployment.

Another thing I haven't been satisfied with AI's job in 2025 so far is code review. While I have had satisfactory luck having my own AI agents help enforce coding standards and some best practices, the real code review which enforces domain knowledge and catches domain or logic bugs that are more complicated any no pointer have been exclusively the domain of human reviewers.

Solving complex open-ended problems that span multiple services has been somewhat possible with cloud code, but still when dealing with ambiguous bugs that's been one or more front ends and one or more back ends, has also remained the domain of a human reviewer.

I'll probably have more to come but we can start with this.

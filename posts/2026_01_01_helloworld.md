---
title: "The Code is the New Boilerplate: Observations from building an itty-bitty blog with 100% browser-based LLM tools"
date: 2026-01-01
category: Development
---

## Intro

This is the first post on "itty-bitty," a tiny project I built to help manage the blog I want to write. The primary goal was simplicity: I wanted a tiny blog platform that is easy to use and manage, and produces static HTML for extemely low resource hosting. 

While not really my intention, this whole thing was built entirely in my browser (more on that later). 

Right now, I'm deploying to Github pages w/ Github Actions to test everything out, but the goal is to move to a self hosted low resource microcontroller (something like a Raspberry Pi Zero) that I can power off of a solar powered battery pack, hamster wheel, or similar.

While the hardware target ultimately is a tiny device on a shelf, the development process exists entirely in the browser.

If you’re curious, the repository lives here -> https://github.com/kbutz/itty-bitty-blog

## The workflow: 100% browser-based

An unexpected but satisfying part of this project was that I haven't opened a terminal or clone a repository on my physical machine. I was able to build, manage, and deploy a custom blog engine using only web-based agents and editors. 

The neat thing here is that I can push updates or write posts from any device, anywhere, without needing a local IDE. Or make edits to the blog platform on the fly from anywhere. Once you push to GH, the new static site gets build and deployed to GH Pages *like magic*.

I tried out [Jules](https://jules.google.com) for browser based agentic coding. Jules is slow, but the idea is great - clone your workspace to Google's cloud, let Gemini iterate, open a PR when it's done. It's very different than my experience with Claude Code, where the work is high quality, fast, and local. This is from Google labs, so in "experiment" mode. It doesn't feel like it will stick around longterm as a Google product, but it is a nice way to work.

I wanted to find another web based IDE option for smaller tweaks (and also don't love editing directly in Github), so ended up on Google's [Firebase Studio](https://studio.firebase.google.com). It has a Gemini agent available, so can do its own agentic coding, and can also connect to your Github. 

For brainstorming/planning, a normal part of my workflow now is chatting with Claude, ChatGPT & Gemini. At work, I would lean heavily into Claude Code for this type of conversation where we build a comprehensive project plan. At work, I would have just used Claude Code for... all of this.

While this is a pretty simple and trivial example, the tools and workflows available are all production grade and easily extendable to an enterprise or "real work" environment. Jules writes real code that real developers can review. You could easily configure Jules, GH Actions, Firebase Studio to deploy something more complicated to a "real" server. My output is static HTML, but the tools are all there for this same browser based workflow to build something *real*.

Here is how the pieces talk to each other:

```text
       [ STRATEGY & LOGIC ]             [ IMPLEMENTATION ]
          Google Gemini  <----------->       Me (Browser)
               ^                             |
               | (Manual Copy/Paste)         | (Direct Edits)
               v                             v
          [ GitHub ] <------------------ [ Firebase Studio ]
               ^  ^         (Commits)        (Agentic Coding)
               |  |
               |  +----------------------- [ Jules ]
                            (PRs)        (Web-based Agent)
               |
               v
        [ GitHub Actions ] -----------> [ Live Site ]
```

* **Gemini:** Acts as the architect. I use it to brainstorm the logic, troubleshoot deployment errors, and write the prompts that I feed to the coding agents.
* **Jules:** A web-based agent that does the heavy lifting. I give it a prompt, and it opens Pull Requests directly in GitHub.
* **Firebase Studio:** This is my "driver's seat" editor. It has integrated Gemini features for quick agentic tweaks, but I also use it for manual content creation.
* **GitHub:** The central hub. I handle merges and minor edits directly in the web interface.

## Quick note on the name

**Itty-bitty** is named after a [Regal Jumping Spider](https://en.wikipedia.org/wiki/Phidippus_regius) that lived at the [Portland Insectarium](https://www.pdxinsectarium.org/), me and my daughter's *favorite* jumping spider, ever. #phidippusregius

## Deployment hurdles

Since itty-bitty builds static pages, they can be hosted anywhere very easily. I wanted an easy way to test this all out, so rather than going for my VPS, or working on securely hosting something from a raspberry pi on my home network right away (which is its own pandora's box of security hurdles), I knew that it would be possible to quickly and reliably host with Github pages. 

I know there are some other lightweight options out there with Google Cloud that would have likely fit neatly with all of the Google based tools I was using, but hosting the pages where the source code lives sounded nice and easy.

Quick Gotcha snag I hit: Initially, I tried a legacy method of pushing built files to a `gh-pages` branch for Github Pages. It was messy and only showed the README. With some troubleshooting via Gemini, I moved to a modern **GitHub Actions** workflow. Now, the site builds as an "artifact" and deploys directly from the Action, keeping the main branch clean.

## A glimpse of the future

What surprised me most about this project wasn’t the code I ended up with, but how the process itself felt. Working this way started to look less like a toy experiment and more like a glimpse of where larger-scale software development could be heading. The same “radical portability” that made itty-bitty convenient also removes a lot of the traditional friction around local environments, dependency management, and machine-specific setup. Instead of bringing the code to your laptop, you hand the work to an agent in its own workspace and tell it what to do next.

Being browser-based isn’t just about hopping between devices—it changes the interface between you, the code, and the coding agents doing the work. That interface could just as easily live in Slack/Matrix/Teams: an agent finishes a task, asks for clarification, or opens a pull request; you respond, course-correct, and move on while it keeps working. Once the interaction looks like this, the constraints shift. You’re no longer limited by how many local repos or editor windows you can keep open, but by how clearly you can plan and communicate work.

Compared to today’s local agentic workflows, that’s a meaningful change. Instead of a single repo and one or two agents running on your machine, you can spin up as many isolated workspaces as you need, review their output through pull requests, and steer them through comments and prompts.

That shift is already showing up in my own day-to-day IC workflow, though local instead of cloud based. I use Claude Code as the entry point to manage a small “team” of coding agents, letting it spin up workspaces, start workers, open pull requests, and iterate based on review comments. As the agents get better, the bottleneck has moved away from writing code and toward planning and review: producing clear, specific technical prompts, and actually (carefully) reviewing the extremely high output of these systems.

Taken together, this points to a fundamental shift in what the software engineer’s job looks like. More of our time moves upstream architecting systems, planning changes, and reviewing outcomes, while the act of writing code becomes increasingly mechanical - the code is the new boilerplate. The real problem-solving happens during planning and reviewing in this new paradigm. That also means the part of the job many engineers find most immersive - the artistic chance to disappear into code and build by hand - shrinks or changes shape. 

The “fun” part isn’t going away, but it is changing quickly, and I worry it will be hard for folks to keep loving this job if they can’t find the “fun” in the new process.

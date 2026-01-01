---
title: "Hello World: My Development Journey with Gemini and Jules"
date: 2026-01-01
category: Development
---

# Hello World: My Development Journey with Gemini and Jules

This is the very first post on my new blog, and it's a bit meta. I'm going to detail the process of how this blog came to be, with the help of some powerful AI tools.

## From Idea to Implementation

It all started with a specific need: an ultra-efficient, minimalist Static Site Generator written in Python. The goal was to have a blog that could be hosted on low-resource hardware, like a Raspberry Pi Zero. With this in mind, I used Google's Gemini to help me refine the requirements for this project and to generate a detailed prompt for an AI coding assistant called Jules.

Once I had the prompt, I handed it over to Jules to do the heavy lifting of the implementation. I created an empty repository on GitHub and gave Jules access to it, allowing it to open pull requests as it worked on the codebase.

## Finding the Right Workflow

As the project took shape, I evaluated various Gemini web-based editor solutions. I was looking for a tool that would allow me to make "in the driver's seat" type changes, like writing this very blog post. This led me to Firebase Studio, which provides a seamless environment for direct interaction and content creation.

## The Deployment Puzzle

One of my key requirements was to have a smooth deployment process using GitHub Actions. My long-term goal is to host this on a very lightweight, possibly battery or solar-powered device like a Raspberry Pi Zero or even a smaller microcontroller.

The initial approach used a legacy method that pushed built files to a separate `gh-pages` branch. This failed because my repository was looking for a build on the `main` branch, resulting in a mismatch where only the README was visible, not the actual site.

## A Modern Solution

With a little help from Gemini, we diagnosed the issue and pivoted to the modern **GitHub Actions** deployment method.

Instead of cluttering the repository history by committing build artifacts to a branch, we updated the `deploy.yml` to upload the build as an "artifact." We then flipped the GitHub Pages source setting to "GitHub Actions," allowing the site to deploy cleanly and directly from the workflow.

## Iterating on the "Micro" Philosophy

With the deployment pipeline fixed, I turned back to Gemini to brainstorm feature enhancements that wouldn't compromise the "itty-bitty" nature of the project. We focused on strategies to keep the file count low and the design clean while adding necessary utility.

The plan now includes:
* **RSS/Atom Feeds:** Updating the Python script to generate a `feed.xml` for subscribers.
* **Zero-Page "About" Section:** Using HTML5 `<details>` and `<summary>` tags to embed bio info directly into the main template, avoiding the need for a separate page load.
* **Smart Styling:** Implementing automatic Dark Mode via CSS media queries and utilizing System Fonts to avoid heavy external requests.

I have synthesized these requirements into a new structured prompt for Jules, ready for the next round of code implementation.

The experience of building this blog has been a fascinating look into the power of collaborative AI development. I'm excited to see where this journey takes me, and I'll be sharing more of my thoughts and experiences here.
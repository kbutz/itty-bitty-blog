---
title: "Down the Rabbit Hole: Coding in the Cloud, From the Cloud"
date: 2026-01-03
tags: [coding-agents, google-cloud, devops, rabbit-hole]
---

A few days ago, I wrote about [my experience creating the `itty-bitty-blog`](https://kbutz.github.io/itty-bitty-blog/2026_01_01_helloworld.html). That project was a test of creating something simple (a static site) using AI tools.

For my next experiment, **[rabbit-hole](https://github.com/kbutz/rabbit-hole)**, I wanted to turn the difficulty dial up. Instead of a static page, I wanted to deploy a containerized Python application to **Google Cloud Run**.

The constraint remained the same: **Create this 100% in the browser.** No local VS Code. No local terminal. Just me, a web browser, and a suite of AI tools.

Here is what I learned about the "Cloud-in-Cloud" development experience, and the specific technical hurdles that lived up to the project's name.

## Part 1: The App (Jules vs. Gemini Chat)

The concept was simple: a visualization tool.

I started by giving the prompt to **Jules** (GitHub's agent). Jules immediately spun up an overly complicated, Node-based architecture. It was technically "code," but it wasn't the *right* code. It felt heavy.

I pivoted to **Gemini Chat (Gemini 3 Pro)**. The difference was stark. It gave me exactly what I visualized: a lightweight Python function coupled with a front-end visualization using `Vis.js`.

**Lesson #1:** Sometimes the "Chat" model (which has less context but perhaps better reasoning for "creative" tasks) outperforms the dedicated "Repo Agent" (which tries to scaffold a massive project structure by default).

## Part 2: The Infrastructure (The "Inception" Problem)

To set up the Google Cloud environment, I used the **Gemini CLI inside Firebase Studio**. Essentially, I was using a cloud-based compute instance (Firebase Studio) to run `gcloud` commands to provision *another* cloud-based compute instance (my Cloud Run service).

It was fascinating, but it introduced a specific type of friction I call the **Sandbox Limitation**.

The Gemini CLI could read my files and edit my documentation perfectly. But every time it tried to *execute* an administrative command to fix a permission error, it failed. The agent was isolated; it didn't share my authenticated `gcloud` credentials.

**The Loop of Frustration:**
1.  Gemini identifies a missing permission.
2.  Gemini tries to run `gcloud ...` to fix it.
3.  **System Failure:** `PERMISSION_DENIED` or `NOT_FOUND` (because the agent is unauthenticated).
4.  **Manual Intervention:** I have to copy-paste the command into the terminal myself.

If I had used a local agent like **Claude Code**, it likely would have had access to my local shell's auth context, bypassing this loop entirely.

## Part 3: The "Silent Killers" (Technical Gotchas)

Because I was committed to the "browser-only" bit, I had to debug infrastructure issues without my usual local tools. Here are the bugs that sent me down the rabbit hole.

### 1. Identity Crisis (Attribute Mapping)
We were using Workload Identity Federation to authenticate GitHub Actions (a security best practice). The setup looked correct, but we kept hitting `unauthorized_client`.

* **The Bug:** The OIDC provider was configured to check for a `repository` attribute, but the provider wasn't actually mapping it! It was only mapping `google.subject`.
* **The Fix:** Explicitly updating the OIDC provider to map `attribute.repository=assertion.repository`.

```bash
gcloud iam workload-identity-pools providers update-oidc ... \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"
```

### 2. The Name Game (ID vs. Number)
We needed to grant the `iam.serviceAccountUser` role to the default Compute Engine service account. The script used the variable `${PROJECT_ID}`.

* **The Bug:** Default Compute Engine service accounts don't use the Project ID in their email. They use the **Project Number**.
* **The Fix:** We had to add a step to programmatically fetch the Project Number via `gcloud projects describe` to target the correct identity.

### 3. The "Wrong Room" (Context Mismatch)
At one point, I was the Project Owner, yet I was getting `PERMISSION_DENIED` errors when trying to modify IAM policies.

* **The Bug:** My Cloud Shell was active in `rabbit-hole-42353939`, but I was trying to modify resources in `rabbit-hole-483120`.
* **The Fix:** A simple `gcloud config set project`. It’s a classic mistake, but harder to spot when you aren't in your familiar local terminal.

### 4. The YAML Trap
The deployment was failing with "unrecognized arguments".

* **The Bug:** The `google-github-actions/deploy-cloudrun` action takes the `flags` argument as a raw string. I had left comments (e.g., `# Keep it at 1`) inside that string, which the CLI interpreted as literal arguments.
* **The Fix:** Removing all inline comments from the YAML configuration.

## Part 4: Cost Control (The Free Tier)
Since this is a demo project, I didn't want a surprise bill. We identified that **Artifact Registry** charges for storage, and every build pushes a new image.

* **The Fix:** We implemented a "Keep Most Recent" policy:
    * Keep the 3 most recent versions.
    * Delete everything else older than 7 days.
    * Added a step in the GitHub Workflow to apply this policy on every deploy.

## Retrospective

Doing this entirely in the browser proved it *can* be done, but we aren't at zero-friction yet. The "Cloud-in-Cloud" abstraction layer adds a fuzziness that makes deep troubleshooting harder than it needs to be.

If I were doing this for a production app tomorrow:
* **For Code:** I'd stick with **Gemini Chat** (it nailed the Python/Vis.js logic).
* **For Infrastructure:** I'd go back to my local terminal. The "Sandbox Limitation" of the remote CLI just isn't worth the hassle yet.

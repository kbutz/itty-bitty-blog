---
title: "Down the Rabbit Hole: Coding in the Cloud, From the Cloud"
date: 2026-01-03
category: tech
tags: [coding-agents, google-cloud, devops, rabbit-hole]
---

A few days ago, I wrote about [my experience creating the `itty-bitty-blog`](https://kbutz.github.io/itty-bitty-blog/2026_01_01_helloworld.html). That project was a test of creating something simple (a static site) using AI tools.

For my next project, **[rabbit-hole](https://github.com/kbutz/rabbit-hole)**, I wanted to try using the same development stack to create an interactive "web of ideas" tool. Using Jules for the async agentic development, followed by Firebase Studio for the editor and minor Gemini-assisted coding, I quickly had a simple working prototype (Python + Vis.js + Wikipedia API).

Cool, it worked. I could play with it in Firebase Studio, and that part took all of 30 minutes.

But wait-I wanted to deploy it to play around with it *outside* of Firebase Studio. Since `rabbit-hole` isn't a pure static website (it requires JS and API calls to be interactive), GitHub Pages was not an option.

There are some built-in deployment options in Jules and Firebase Studio (e.g., "Deploy to Firebase," "Deploy to Google Cloud") which I could have tried, but those types of solutions rarely feel production-grade. I like Infrastructure as Code (IaC), and I like my personal projects to reflect systems and workflows that I *could* use in a real-world business environment.

I turned to GitHub Actions again. Using Jules, I got an initial action set up. The next several hours were spent trying to configure `gcloud` and the GitHub workflow. I stubbornly stayed "in browser" here, using Firebase Studio's terminal with the Gemini CLI. I had to do some troubleshooting in the Google Cloud Console for this as well.

Ultimately, it worked, but it took many times longer than it would have had I done the deployment setup locally with Claude Code or the local Gemini CLI. One self-inflicted issue: I was using Gemini 2.5 via the Firebase Studio Gemini CLI. It is simply nowhere near as powerful as Gemini 3 or the models available in Claude Code.

In the end, it was very neat to set up my cloud deployment *from* that very same cloud. (Firebase Studio provisions a `gcloud` instance; I ran Gemini CLI on that instance to run `gcloud` to set up the deployment instance 🤯). But it was not at all practical. I wonder what my experience would have been if I had been using Gemini 3 from that cloud-based Gemini CLI session, since Gemini 3 Pro *did* ultimately solve the problem-just from Gemini Chat, not the CLI.

## Part 1: The App (Jules vs. Gemini Chat)

For the app idea, I started with a simple, meandering prompt given directly to **Jules**. Jules seemed like it got the idea right, but the execution was too complicated-a big Node.js server that was heavier than I wanted for my simple relationship explorer tool.

**Gemini Chat** got the same prompt (on Gemini 3 Pro) and provided a working solution in two files. Much better.

This is a good reminder to workshop your prompts before you give them to your agent. Claude Code does this very well with its "planning mode." Jules has a planning mode also, but I have not tried it out yet to compare.

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

It is also important to note that I was not running Gemini 3 in my cloud-based Gemini CLI version. This whole issue may have disappeared with the more capable Gemini 3 model - *we'll never know*.

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

* **The Fix:**
    * **Billing Alerts:** Gemini proactively suggested (and gave instructions for) setting up Billing Alerts to warn me if costs exceeded $1.00-a crucial safety net for experiments like this.
    * **Lifecycle Policy:** We implemented a "Keep Most Recent" policy that keeps the 3 most recent versions and deletes everything else older than 7 days.
    * **Automation:** Added a step in the GitHub Workflow to apply this policy on every deploy.

## Retrospective

Doing this entirely in the browser proved it *can* be done, but we aren't at zero-friction yet. The "Cloud-in-Cloud" abstraction layer adds a fuzziness that makes deep troubleshooting harder than it needs to be.

If I were doing this for a production app tomorrow, I'd simply use **Claude Code** to write the code, manage the GitHub lifecycle, and set up the cloud environment. I’d bet that doing it this way would have taken 20 or 30 minutes max - not the hours I spent banging my head against the keyboard and cursing the poor model.
# Phoenix Demo Video Script

A three minute video script for the hackathon submission. Total runtime targets 2:55 to leave buffer.

## Recording setup

- 1080p minimum, 4K ideal
- Quiet environment, USB microphone (not laptop mic)
- Screen recorder: OBS Studio (free, professional)
- Pre-stage browser tabs: GitLab pipeline page, Phoenix dashboard, GitLab MR list
- Have the demo GitLab repo ready with a broken pipeline waiting (run `make seed` beforehand)

## Tone

Confident, technical, no marketing fluff. Engineers watching this should think "this person built a real thing". Avoid superlatives, avoid hype, let the product do the talking.

---

## Shot list

### Scene 1 - Hook (0:00 - 0:15)

**Visual:** Slack notification animation. The message reads "🚨 #incidents Pipeline failed - production deployment blocked".

**Voiceover:**
> "Two AM. A pipeline breaks. An engineer wakes up. They open their laptop, find the failing job, regenerate a lockfile, push a fix, go back to sleep. Now imagine if none of that had to happen."

### Scene 2 - The Problem (0:15 - 0:35)

**Visual:** Static slide with the math:
```
50 developers × 6.5 hours/week × 50 weeks = 16,250 hours/year
At $150/hour = $2.4 million per year
```

**Voiceover:**
> "Engineering teams lose six and a half hours per developer per week to broken pipelines. For a fifty person team, that is two point four million dollars a year burned on problems an AI can solve completely. Not assist with. Solve."

### Scene 3 - Introducing Phoenix (0:35 - 0:55)

**Visual:** Phoenix logo, then transition to the architecture diagram from the README.

**Voiceover:**
> "This is Phoenix. An autonomous multi-agent system built on Google ADK and Gemini. When a GitLab pipeline fails, Phoenix's three specialized agents work together to diagnose the failure, pick a fix, apply it in a sandbox, and open a merge request."

### Scene 4 - Live Demo Setup (0:55 - 1:10)

**Visual:** Switch to GitLab UI showing a failed pipeline. Red X on the test stage.

**Voiceover:**
> "Here is a real GitLab pipeline that just failed. Someone bumped react-table to version 8.20 and now there is a peer dependency conflict. The test stage cannot even start because npm install crashed."

### Scene 5 - The Dashboard Lights Up (1:10 - 1:45)

**Visual:** Switch to Phoenix dashboard. Show the reasoning trace streaming in real time. Each entry appears with its timestamp.

```
[14:32:01] PERCEIVE   Fetching pipeline 4827...
[14:32:04] DIAGNOSE   Classification: dependency_conflict
                      Confidence: 0.89
[14:32:07] STRATEGIZE Selected: regenerate_lockfile
[14:32:08] EXECUTE    Spawning sandbox phoenix-sandbox-001
[14:34:11] VERIFY     Pipeline 4828 succeeded in 2m 41s
[14:36:52] DECIDE     Merge request !192 created
```

**Voiceover:**
> "Phoenix's Diagnostician agent reads the log, calls the GitLab MCP server through a tool, and classifies the failure with eighty nine percent confidence. The Strategist picks regenerate-lockfile. The Executor applies the fix in a Cloud Run sandbox, triggers a verification pipeline, and opens a merge request. Every decision streams live to this dashboard."

### Scene 6 - The Merge Request (1:45 - 2:10)

**Visual:** Switch to GitLab MR view. Show the auto-generated MR titled "Phoenix: Auto-fix dependency_conflict in pipeline 4827" with the full reasoning trace in the description.

**Voiceover:**
> "Phoenix never pushes to main directly. The fix arrives as a merge request that a human still reviews. The description contains the full reasoning trace, the diagnosis confidence, the strategy chosen, and the verification result. Everything is auditable."

### Scene 7 - Memory and Learning (2:10 - 2:35)

**Visual:** Side by side: first run versus second run of the same kind of failure. Highlight the time difference. Show the Strategist saying "Memory hit" the second time.

**Voiceover:**
> "Phoenix learns. Every successful fix is stored in Firestore by signature. The next time the same kind of failure shows up, the Strategist queries memory first, finds the proven fix, and skips straight to execution. Time to resolution drops to near zero on recurring problems."

### Scene 8 - Architecture and Compliance (2:35 - 2:50)

**Visual:** Compliance checklist sliding in:
- ✅ Built on Google ADK
- ✅ Powered by Gemini 2.0
- ✅ GitLab MCP integration
- ✅ Runs entirely on Google Cloud
- ✅ Open source, MIT licensed

**Voiceover:**
> "Phoenix is built on Google ADK, runs on Gemini through Vertex AI, integrates the GitLab MCP server deeply, and deploys entirely to Cloud Run. No third party orchestrators. No competing frameworks. Fully open source under MIT."

### Scene 9 - Close (2:50 - 2:55)

**Visual:** Phoenix logo with the tagline "Rise from the ashes."

**Voiceover:**
> "Phoenix. Rise from the ashes."

---

## Editing checklist

- [ ] All four code agents in the dashboard are visible at least once
- [ ] At least one GitLab MCP tool call is highlighted on screen
- [ ] The reasoning trace is readable (zoom in if needed)
- [ ] The final merge request screen is on screen for at least three seconds
- [ ] Background music is subtle and royalty free (consider YouTube Audio Library)
- [ ] No audio dropouts
- [ ] Subtitles added for accessibility (required by hackathon rules for non-English)
- [ ] First three minutes only - anything past that will not be evaluated

## Filming tips

- Record each scene separately and stitch in post. Trying to nail the whole thing in one take wastes time.
- Always have a backup successful run of Phoenix before recording. Live demos fail.
- Pre-warm the Cloud Run instances by running a dummy pipeline first. Cold starts will make Phoenix look slow.
- Speak slightly slower than feels natural on camera. It will sound right on playback.

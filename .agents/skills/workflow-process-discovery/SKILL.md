---
name: workflow-process-discovery
description: "Turn a narrated process transcript into steps sorted into scripts, candidate skills, and human gates. Ordered stages over exact Skill Core skills."
---

# Process Discovery

Turn a narrated process transcript into steps sorted into scripts, candidate skills, and human gates.

> Generated from `workflows/process-discovery/workflow.toml` by `scripts/project_skills.py`.
> Edit the manifest, not this file.

## Stages

1. **decompose** - skill `domain-modeling`
   - output: `stages/01-decompose/steps.md`
   - Break the transcript into atomic steps. One action per step, with its inputs and outputs named.

2. **interrogate** - skill `grill-me`
   - output: `stages/02-interrogate/open-questions.md`
   - Surface unstated assumptions, missing error paths, and steps whose description hides a judgment call.

3. **sort** - skill `to-spec`
   - output: `stages/03-sort/classification.md`
   - Apply the three sorting questions to each step, in order. First yes wins.

4. **approve** **(approval gate)** - skill `to-questionnaire`
   - output: `stages/04-approve/approved.md`
   - Human review of the classification. Every GATE and every SKILL is confirmed before anything is written.

5. **emit** - skill `skill-creator`
   - output: `stages/05-emit/manifest.md`
   - Write the approved artifacts:

Each stage reads the previous stage's output file, not the whole prior
conversation. That bounds context and makes resume and retry possible.

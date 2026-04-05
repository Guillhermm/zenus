---
name: review-pr
trigger: review-pr
description: Review all changes on the current branch vs main and give structured feedback
---

Perform a thorough code review of the changes on the current git branch compared to the main/master branch.

Steps:
1. Identify the base branch (main or master).
2. Run `git diff <base>...HEAD` to get all changed lines.
3. Analyse the diff for: correctness, security issues, performance concerns, missing tests, style inconsistencies, and documentation gaps.
4. Output a structured review with sections: Summary, Issues (Critical / Major / Minor), Suggestions, and Verdict (Approve / Request Changes).

{args}

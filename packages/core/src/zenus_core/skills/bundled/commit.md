---
name: commit
trigger: commit
description: Stage all changes and commit with a descriptive, conventional-commits message
---

Stage all tracked changes in the current git repository and commit them with a well-written, conventional-commits-style message.

Steps:
1. Run `git diff --stat` to understand what changed.
2. Run `git add -A` to stage all changes.
3. Generate a concise commit message that follows the pattern: `<type>(<scope>): <subject>` where type is one of feat, fix, docs, refactor, test, chore.
4. Commit with the generated message.

{args}

---
name: simplify
trigger: simplify
description: Review recently changed code for quality and simplify it without changing behaviour
---

Review the code that was most recently modified or is currently staged/unstaged in the git repository.

Look for:
- Duplicated logic that can be extracted into a helper
- Overly complex conditions that can be simplified
- Dead code or unused variables
- Premature abstractions that add complexity without value
- Missing early returns that would reduce nesting

For each issue found, explain the problem and provide the simplified version inline.

Target: {args}

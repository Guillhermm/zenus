# The Zenus Manifesto

*Computing driven by intent, not commands.*

---

## The Problem with How We Use Computers

We have spent fifty years teaching people to speak the language of machines.

To copy a file, you learn `cp`. To find a process, you learn `ps aux | grep`. To install a dependency, you learn which package manager this distribution chose, and whether it uses `apt`, `dnf`, `pacman`, or something else entirely. To undo a mistake, you hope you have a backup.

Every one of these things is a translation problem. The user knows what they want. The system knows how to do it. The gap between them is an interface — and that interface, for most of computing history, has been built for the machine's convenience, not the human's.

The shell is a marvel of engineering. It is also, fundamentally, a foreign language that billions of people are expected to learn just to operate their own computers.

We think this is backwards.

---

## What We Believe

**Intent should be the interface.**

When you tell Zenus "organize my downloads by file type", you are expressing an intent. You are not asking to learn the difference between `mv` and `cp`, or to remember whether glob patterns use `*` or `%`, or to think about whether the destination directory exists yet. You are expressing a goal — and that goal is the only thing that should matter.

**Safety must be structural, not advisory.**

Most AI tools that touch your system ask the LLM to "be careful". That is not safety — it is hope. Zenus enforces safety through architecture: every LLM output is validated against a typed schema (Intent IR) before anything executes. Risk levels are declared. Destructive operations require confirmation. Every step is a transaction that can be reversed. The system cannot execute something it cannot first describe precisely.

**Reversibility is a first-class feature.**

Mistakes happen. The measure of a good system is not whether mistakes are prevented (they cannot always be), but whether they can be corrected. `zenus rollback` is not an afterthought — it is a promise. Every action Zenus takes is recorded before it runs. You can always go back.

**Local-first, open-source, no lock-in.**

Your system is yours. The AI that operates it should be too. Zenus runs entirely on your machine. It works with any LLM — including models that never leave your hardware. No telemetry by default. No vendor dependency. The source code is public and the license is GPL.

**The shell is not the destination.**

We are building Zenus as a shell today because that is where the work is. But the design decisions we make now — the typed IR, the sandboxed execution model, the privilege tiers, the knowledge graph, the transaction log — are not shell decisions. They are OS decisions. The architecture is being built for a future where the AI intent layer sits closer to the hardware, where scheduling and resource management are mediated through intent rather than syscalls.

That future is far away. But every line of code we write now is written with it in mind.

---

## What Zenus Is Today

Zenus v1.1.0 is a production-ready natural language shell for Linux.

It can manage your files, monitor your system, control services and packages, run git workflows, automate browser tasks, and answer factual questions using live web search — all through plain language. It remembers what worked and what failed. It warns you before repeating a known mistake. It can undo what it did.

It is not magic. It is not infallible. It will occasionally misinterpret your intent, and that is why dry-run mode and rollback exist. It is a tool — a well-built one — that makes Linux more accessible and more efficient for people who know exactly what they want but do not want to memorize the syntax to get it.

---

## What Zenus Is Not

**Zenus is not a coding assistant.**

There are excellent tools for that — Aider, Claude Code, Cline, Cursor. Zenus does not compete with them. It operates your system; they modify your source code. The problems are different. The architecture is different. The safety requirements are different.

**Zenus is not an OS yet.**

The long-term vision is real, and we are serious about it. But we will not pretend to be something we are not. Today, Zenus is a Python process running on Linux. The OS vision is the destination, not the current address.

**Zenus is not a cloud service.**

There is no Zenus server processing your commands. There is no account to create, no subscription required, no data being collected. Your commands stay on your machine. The only network activity is what you configure: the LLM API you choose, and web searches when the LLM determines current data is needed.

---

## The Path Forward

The roadmap is public. The phases are honest about what is done and what is aspirational.

Near-term: harden security, complete voice, add MCP interoperability so Zenus tools are available to any compatible AI client.

Medium-term: multi-machine orchestration, richer integrations, the plugin ecosystem that lets the community extend Zenus without forking it.

Long-term: the OS. A Linux distribution where the AI intent layer is not a userspace application but a core system component — where the gap between what you want and what your computer does is measured in milliseconds, not in learning curves.

---

## Why This Matters

The next billion people to use computers will not learn bash. They should not have to. The interface should adapt to humans — not the other way around.

Zenus is a step toward that. One system, one user, one intent at a time.

---

*Guilherme Zeni — March 2026*

*[github.com/Guillhermm/zenus](https://github.com/Guillhermm/zenus)*

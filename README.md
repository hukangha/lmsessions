# lmsessions

List, search, view, remove or resume Claude Code, Codex, OpenCode and Google Antigravity sessions in a vim-ish style

Run with no arguments for the interactive menu:

`/`  to search

`v` to open vim viewer

`s` to sort

Requires Python 3.10+

Change a session's workspace:

```sh
lmsessions mv <session-id> [directory]
lmsessions mv <source-directory> [directory]
```

The destination defaults to the current directory and must already exist. A source directory selects sessions from that directory across all agents (without recursion). The command updates workspace metadata and keeps transcript files at their original paths. Run `lmsessions` or `lmsessions -l` in the destination to see the reassigned sessions. Use `agent:session-id` when an ID is shared by multiple agents.

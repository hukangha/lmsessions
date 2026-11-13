# lmsessions

List, search, view, remove or resume Claude Code, Codex, OpenCode and Google Antigravity sessions in a vim-ish style

Run with no arguments for the interactive menu:

`/`  to search

`v` to open vim viewer

`s` to sort

Requires Python 3.10+

Use `lmsessions ls` for a plain list in the current directory, or `lmsessions ls -a` for every directory. Running `lmsessions` without a subcommand opens the interactive picker.

Move or copy sessions:

```sh
lmsessions mv <session-id> [directory]
lmsessions mv <source-directory> [directory]
lmsessions cp <session-id> [directory]
lmsessions cp <source-directory> [directory]
```

The destination defaults to the current directory and must already exist. A source directory selects sessions from that directory across all agents (without recursion). Local `mv` updates workspace metadata, keeping transcript files at their original paths. Local `cp` creates independent copies with new session IDs, printed in the output. Run `lmsessions` or `lmsessions ls` in the destination to see them. Use `agent:session-id` when an ID is shared by multiple agents.

SSH destinations are supported for both commands:

```sh
lmsessions mv <session-id> user@host:/work/project
lmsessions cp <source-directory> server-alias:~/work/project
lmsessions cp <session-id> ssh://user@host:2222/work/project
```

SSH uses your usual keys, password prompts and SSH config. The remote host needs Python 3.10+ and an existing destination workspace; this program is sent over SSH, so remote installation of `lmsessions` is optional. Transfers include the session's transcript, owned database rows and companion files (Claude subagents/tool artifacts, Antigravity brain/conversation/annotation data). They import into native agent stores, preserving unrelated remote sessions. Remote copies retain the original session IDs; existing destination IDs/files are refused. Database row IDs are remapped where needed to preserve related records.

Remote `mv` removes the source only after receiving a verified import receipt, confirming destination listing, and checking the source has not changed during transfer. `cp` always retains the source (`mv --keep-source` is an alias). A failed or interrupted transfer retains source data; a completed remote import whose acknowledgement is lost may leave a remote copy. A batch can be partially completed across different agent stores if a later commit or source cleanup fails. Local copying of compressed Codex rollouts uses the existing optional zstd support to update the copied session identity.

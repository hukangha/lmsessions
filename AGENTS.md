# lmsessions — code map for agents

Single executable Python 3.10+ script (`./lmsessions`, stdlib only). Lists,
searches, views, removes and resumes coding-agent sessions (Claude Code, Codex,
OpenCode, Google Antigravity), either as a plain list or an inline interactive
picker. No tests, no build step; verify by running it.

## Entry point

`main()` parses `-l/--list` and `-a/--all`, then:

| invocation        | behavior                                  |
|-------------------|-------------------------------------------|
| (none)            | `interactive_menu($PWD)`                  |
| `-a`              | `interactive_menu(None)` = every dir      |
| `-l`              | `list_sessions($PWD)`                     |
| `-l -a`           | `list_sessions(None)`                     |

`cwd` is `Path | None` everywhere; `None` means "every directory" and also
turns on the CWD column.

## Data model

- `Session(agent, id, mtime, size, prompts, title, path, cwd)` — one row.
  `path` is the transcript file (the opencode db for opencode, the Antigravity
  transcript log or conversation db for agy).
- `Turn = (role, timestamp, body)`; `Hit = (snippet, match_start, match_end)`.
- `all_sessions(cwd)` merges every `Agent` in `AGENTS`, sorted by mtime
  **oldest first**.

## Agents (`Agent` subclasses, one instance each in `AGENTS`)

Each implements `sessions(cwd)`, `remove(s)`, `resume(s)`, `transcript(s)` and
`view(s, view, tmpdir, options)` (the vim viewer). `agent_of(s)` looks one up by
`s.agent` name. `removable` / `viewable` are class flags (default True); agy
turns `viewable` off, and the picker/menu show a "not supported yet" message
instead of calling that method.

- **ClaudeAgent** — `~/.claude/projects/<project>/*.jsonl`, where `<project>` is
  the cwd with every non-alphanumeric char replaced by `-` (`project_name`).
  `title_and_cwd` scans the JSONL: latest `custom-title` wins over latest
  `ai-title`, else first real user prompt (synthetic `<local-command…>` /
  `<command-name…>` records are skipped and not counted as prompts). Sessions
  are filtered again by realpath of their `cwd` because distinct paths can
  collide in one project dir. Remove = unlink file.
- **CodexAgent** — `${CODEX_HOME:-~/.codex}/state_5.sqlite`, table `threads`
  (`id, name, title, updated_at(_ms), rollout_path, cwd`). Prompts are counted
  from `response_item`/`message` records with role `user` (newer Codex, skipping
  the `<environment_context>`-style records Codex injects), or from
  `event_msg`/`user_message` records (older Codex) when a rollout has no
  `response_item` user message — never both, so the two kinds cannot double
  count. Old rollouts are stored
  zstd-compressed: a `rollout_path` whose file is missing is retried as
  `.jsonl.zst`, which `read_jsonl`/`file_size` decompress (stdlib `compression.zstd`
  on 3.14+, else the `zstandard` module; without either, that rollout reads
  empty and its size is the compressed one). Remove deletes the thread's rows
  from every table that has a `thread_id` /
  `parent_thread_id` / `child_thread_id` column, then the `threads` row, then
  the rollout file. This schema is version-dependent — re-check on Codex
  upgrades.
- **OpenCodeAgent** — `${XDG_DATA_HOME:-~/.local/share}/opencode/opencode.db`.
  Read-only by default (`URI ?mode=ro`); `connect(readonly=False)` only for
  removal. `session_v2` left-joins an aggregate over `session_message` for
  size/prompts. Remove = `DELETE FROM session_v2` with foreign keys on.
- **AgyAgent** (Google Antigravity CLI, `agy`) —
  `~/.gemini/antigravity-cli/conversation_summaries.db`, read-only, one row per
  conversation: `conversation_id, title, preview, last_modified_time,
  workspace_uris`. `workspace_uris` is a JSON list of `file://` URIs; the first
  is the session cwd. `preview` holds the generated title when `title` is empty,
  else the first `USER_INPUT` prompt is the fallback. Prompts are counted from
  `brain/<id>/.system_generated/logs/transcript.jsonl`; a conversation without
  that log has no transcript, prompts or fallback title, and uses its `.db` for
  `path`/size (some subagent conversations are like this). That log is also the
  transcript source:
  `USER_INPUT` records carry the prompt inside `<USER_REQUEST>…</USER_REQUEST>`
  (metadata after it is dropped), and `PLANNER_RESPONSE` records carry assistant
  text plus `tool_calls`; tool-result record types are skipped. Tool args are
  JSON-encoded strings and use Antigravity's own names (`CommandLine`,
  `AbsolutePath`, …), so `ARG_KEYS` renames them for `tool_marker`. Resume =
  `agy --conversation <id>`. Remove deletes the summary row, the
  `brain/<id>/` directory, `conversations/<id>.db` (and its `-shm`/`-wal`
  files) and `annotations/<id>.pbtxt`. The viewer is not implemented
  (`viewable` False). This layout is version-dependent — re-check on `agy`
  upgrades.
- `transcript()` normalizes each agent's format to `(role, ts, body)` with
  tool calls reduced to one-line `tool_marker` text. Raw tool results and
  reasoning/thinking are dropped. Claude's transcript also skips records off the
  live branch (see the viewer section), so search omits rewound content.
- `resume()` → `exec_agent()`: chdir to the session's `cwd` (if it still
  exists) and `execvp` the agent CLI. It replaces the process, so it never
  returns; `resume_session()` only catches `OSError`.

## Rendering

`COLUMNS` defines label/width/sort-attr/alignment; `columns(cw)` appends CWD
when `cw > 0`. `header`, `header_spans` (click targets), `format_row` must all
agree on widths — the picker slices/truncates by them. `sort_key(attr)` sorts
strings case-insensitively. `header(cw, sort_attr, reverse)` reverse-videos the
sorted column and appends `↑`/`↓` inside it (or in the following gap when the
label already fills the width, as PROMPTS does); the escapes are zero-width, so
click spans are unaffected.

## Listing / search

- `list_sessions()` prints the header plus one `format_row` per session.
- `find_hits(s, rx)` searches the title and every transcript line, returning
  de-duplicated ±120-char snippets (`snippet`).

## Session viewer (`v`)

`v` returns `("view", session, ...)` for every viewable agent (not agy, which
shows a message in the picker). The menu loop then opens `edit_view_options()`;
Enter there passes the saved options to `view_session()` and opens vim, Esc
returns to the picker. `view_session()` calls
`agent_of(s).view()`, which fills a `ViewBuilder` (lines plus fold ranges); it
writes that into a temp file and runs `vim` on it; the picker has already
restored the terminal by then, and the caller re-enters it with the same sort,
marks and focus afterwards. The temp dir is removed when vim exits. The buffer
is readonly with every section folded (`foldmethod=manual`, `foldcolumn=1`,
`normal! zM`);
`za`/`zo`/`zc`, clicking the fold column or double-clicking a section header
toggles a fold.

`message_section()` and `tool_section()` build the shared USER/ASSISTANT/
THINKING and tool-call folds; `view_header()` writes the title block.

`ViewOptions` (`max_messages`, `normal_parts`, `raw_parts`, `raw`,
`accumulative`) is kept by the menu loop. `v` opens `edit_view_options()` first;
Enter there renders with the options, Esc returns to the picker. The normal-mode
list is every foldable section kind (`user`, `assistant`, `system`, `thinking`,
`tool`, `note`, `attachment`, `api`, `loop`, `procedure`); the roles also filter
API request messages, and deselecting a section hides it (`loop`/`procedure` hide
only their grouping fold). Normal mode also
shows the last `max_messages` entries of each API request body in full content,
eliding the front with `......`; the system prompt heads the list and counts as
one entry, so a small limit omits it (`0` = none, `-1` = the whole body). Raw mode
(`raw`) shows only reconstructed request bodies, filtered by `raw_parts` (roles
and block kinds): the latest request, or with `accumulative` every request's
growing prefix, marking messages added since the previous request with `+`.
Non-Claude views accept `options` and ignore it.

All three views feed `TurnBuilder`, so they share one turn shape:
`render_turn()` writes USER, wraps repeated loops (and any items before the
first response) in one PROCEDURE fold, and renders the final ASSISTANT text
after it. `final_text_for()` picks that text — the last one with no tool call
or later loop after it — and a loop that would be empty once the text is hoisted
does not count. A loop is one model response: for Claude an API request and what
it emitted, for Codex the response items up to the following tool outputs, for
OpenCode one assistant message. `render_loop()` labels the loop with its
request/thinking/tool-call counts, or its assistant-text count when it has
neither.

`codex_view()` walks a rollout's records in order: user prompts (one kind, never
both `response_item`/`message` and `event_msg`/`user_message`, as in
`transcript`), reasoning summaries, `function_call`/`custom_tool_call`/
`web_search_call` with outputs paired by `call_id`, and assistant `output_text`.
The duplicate `event_msg` records, `token_count`, turn context and developer
messages are skipped; `turn_aborted` and error events become notes.

`opencode_view()` walks `session_message` rows via `OpenCodeAgent.messages()`:
`user` text, then an assistant message's content parts — `reasoning`, `text`
and `tool`, where a tool part carries its own input and result state (status
`error` is marked `✗`), so no pairing pass is needed. `compaction` and `system`
rows become notes; `idle` and `synthetic` rows carry no conversation text.

`claude_view()` parses the records itself rather than reusing `transcript()`,
because that deliberately drops thinking, tool results and injected context.
Each API request opens a loop, and consecutive requests with no items between
them share it. A trailing request-only loop is carried into the following user
turn when its timestamp matches that user record: Claude logs a turn's API
request just before its user message. USER/ASSISTANT fold headers carry a preview of the body (first two
sentences or 100 characters). Results pair with calls by `tool_use_id`;
`toolUseResult` wins over the model-visible `tool_result` text (Edit/Write
`structuredPatch` as a unified diff, Bash `stdout`/`stderr`, Read
`file.content`, WebFetch `result`). A tool output longer than
`CLAUDE_VIEW_LINES` (300) shows that many lines and writes the whole text to a
temp file, whose path is the last line (`gf` opens it). System notes cover
compaction, slash commands, warnings, API errors, user interrupts and
permission denials; sidechain records are prefixed `[subagent]`. Each
`api-request` shows params, a shape summary and up to `max_messages` messages of
the reconstructed body whose role is selected (head/tail summaries with `......`;
`-1` prints every such message in full). `isMeta` user records, synthetic `<local-command…>`/`<command-name…>`
user text, `turn_duration`, most attachment types (`VIEW_ATTACHMENTS` is the
whitelist) and the duplicated `api-request-blob`/`api-request-shape` records are
skipped.

`claude_request_body()` reconstructs one request's complete sendable body: walk
`base` to the root, take the last `keep` messages of the chain, append `tail`,
resolve each hash from `api-request-blob`, and — for bodies the log omitted —
rebuild it from contiguous same-role user/assistant records (a string content
becomes a `text` block) and verify it with `claude_message_hash()` (SHA-256 of
compact, sorted-key JSON). It reattaches `cacheControl` paths to the blocks they
mark, parses the stringified tool `input_schema`, and returns a `RequestBody`
(`payload()` strips `betas`, which is a request option, not a body field).
Unrecoverable hashes become placeholders and are listed in `missing`.
`render_request()` and `render_raw_view()` use it.

A rewind leaves the abandoned branch in the jsonl. `claude_active_uuids()` keeps
only records on the live branch: start from the newest conversation record (or
the last-prompt leaf when that record is newer, for a rewind with no new
message) and follow `parentUuid` to the root, using `logicalParentUuid` to cross
a compaction boundary. `claude_view()` skips records whose `uuid` is not in that
set (sidechain records are kept). `claude_active_requests()` does the same for
API requests, which have no `uuid`: a request is live when the next meaningful
conversation record is on the live branch. `title_and_cwd()` uses the same
filter, so the prompt count and fallback title ignore rewound prompts.

`vim_viewer_script()` creates manual folds **innermost-first** (sorted by range
length): creating an outer fold first makes Vim raise that whole fold's level
for every range nested in it. `view_session()` sets `nomodeline` in `--cmd` and
again before `:edit`, so transcript text cannot run as a modeline.

## Interactive picker (`pick_sessions`) — the bulk of the code

Draws an inline TUI below the cursor using absolute-position writes: one fixed
frame of `term.lines - 3` body lines; each row is 1 session line + N snippet
lines when `hits` is set (all hits for current/marked rows, first hit
otherwise). It turns autowrap off (`?7l`) so overlong lines can't shift the
cursor-up count, hides the cursor (`?25l`) so it can't blink at the frame's
top-left corner, and restores both on exit. Mouse reporting (`?1000/?1006`) is
enabled only if `cursor_row()` (DSR) gets an answer, needed to map click
coordinates.

A resize redraws at the new size: `SIGWINCH` writes through
`signal.set_wakeup_fd` to a pipe, and `next_key()` selects on stdin and that
pipe, returning `"resize"`. `resize()` re-measures the terminal, re-queries
`picker_top`, and erases the old frame (`ESC [ J`) before the next frame is
drawn — otherwise the fixed cursor-up count would leave stale lines behind.

State: `cur`, `top`, `marks` (row indexes), `status`, `sort_attr`/`reverse`,
`hits`, `focus` (session to re-highlight when returning from a sub-action).

Keys: `j/k`/up/down arrows move, `Ctrl+f/b` page, `g/G` first/last,
`Tab`/`→`/`l` cycle the sort through the header columns (TITLE included) and
`Shift+Tab`/`←`/`h` cycle it backwards, `s` toggles the sort direction,
`J/K`/Shift-arrows toggle the row stepped onto, plus the row being left when the
run starts or reverses direction (so holding it toggles a run and reversing
un-toggles it back; at a list end a held key does nothing), `Space` toggle the
current row, `y` copy id, `/` incremental search, `v` open the view options,
then Enter opens the viewer, `Delete` remove, `Enter` resume — or, with several
rows marked, open a
submenu of just those rows — `q` quit, `Esc` quit (or back when `hits` is set
or `can_back` says the page was opened from another). Clicking a
header sorts (same header toggles direction); marks and cursor follow sessions
by identity.
Clicking a row copies the CWD (or, outside that column, the transcript's
directory).

Mouse wheel: terminals cannot tell a wheel from a trackpad, so event cadence
decides. `next_key()` takes a timeout, and a wheel notch (button 64 up, 65
down) is held for one gap (30 ms): a companion event arriving first makes the
run a trackpad scroll, the timeout makes the notch a mouse's. A mouse notch
drags `cur` and leaves scrolling to `frame()` once the highlight would leave
the body. Trackpad events move `top` and `cur` together, so the highlight keeps
its row on screen, and stop dead at either end (`bottom_top()` is the lowest
`top` where the list's tail still fills the body), so the highlight never
drifts there. Holding each notch costs every notch one gap of latency.

Returns `(action, payload, current, sort)` where `sort` is the
`(attribute, reverse)` the list ended up in:
`remove` → the picker's `marks` (possibly empty; the caller falls back
to `current`); `submenu` → the marked `Session`s; `resume`/`view` → the
`Session`; `search` → pattern; `back` → `None`; `None` → cancelled. Passing
`sort` back in re-sorts `rows` to it, so the order survives every return to the
picker.

## Menu loop (`interactive_menu`)

Wraps the picker and keeps a `history` stack of
`(rows, hits, cw, filters, marks, base)` — one entry per successful search or
Enter-opened submenu, so `Esc` on such a page reopens the page it came from.
`base` is a submenu's session list; `None` means every session for the cwd.
Additional searches compose:
`filters` is cumulative (rows must match all regexes, case-insensitive), and
`hits` shown always come from the latest filter. The picker's `sort` is kept
here and handed back to every picker invocation, so the order survives search,
back and removal. The `view_options` edited before `v` lives here too and is
passed to every `view_session()`.

After a removal it keeps the history stack, pruning the removed sessions from
every page (and dropping a page left empty), so `Esc` still walks back through
it. It then rebuilds `rows` with `rebuild_rows()`, reapplying all filters, and
falls back to the page above if the current page emptied; a submenu keeps its
scope, with the removed sessions dropped from `base`. That helper keeps
the sessions in the order they were last shown (unseen ones last) rather than
`all_sessions()`'s oldest-first order, so ties of the sort column do not
reshuffle after a delete. The highlight keeps its row index into the rebuilt
list (clamped to the last row) instead of jumping to the top. Confirmation
(`confirm_remove`) semantics: `Enter` deletes, `Esc` returns with `marks` kept.

## Terminal plumbing

- `read_key(fd)` disambiguates bare Esc from escape sequences by waiting 25 ms;
  decodes arrows and Left/Right, Shift-arrows, Shift+Tab, Delete, and SGR mouse
  `ESC [ < b ; x ; y M` into a tuple. Unknown sequences return `""`. Bytes read
  while probing replies are stashed in `_pending` (`read_byte`).
- `terminal_color(ps)` asks the terminal for colour 10 (fg) or 11 (bg) via OSC;
  `shade_codes()` derives row-highlight and keyword-highlight shades from the
  bg (20/40 steps away), and for a row that is both current and marked a bg
  midway between the terminal bg and fg. Falls back to 256-color 236/240, or to
  the row highlight when only the fg is unknown.
- `copy_to_clipboard()` prefers wl-copy/xclip/xsel, writing both CLIPBOARD and
  PRIMARY, and falls back to OSC 52 (silently ignored by some terminals).
- Modal prompts (`ask_enter`) use cbreak mode
  and accept `Esc`/`Ctrl+O` as "back".

## Invariants / gotchas

- Marks are indexes into the *current* `rows`; any re-sort/re-filter must remap
  them by session identity, not position.
- Picker frame height and cursor-up count must stay in lockstep; a row's height
  depends on `hits`, and `top` is advanced until the visible window fits.
- Widths are character counts, not display cells — titles with wide glyphs can
  misalign.
- Removal is immediate and permanent (no trash/undo).
- `interactive_menu` requires a tty; otherwise it prints a hint and exits 1.
- Only documented behavior: sessions are sorted by mtime ascending (oldest at
  top) unless the user clicks a header, presses `Tab`/`→`/`l` or
  `Shift+Tab`/`←`/`h` (cycles columns) or `s` (toggles direction) (the header
  then shows the sorted column and direction).

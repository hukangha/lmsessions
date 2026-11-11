# lmsessions

List, search, view, remove or resume Claude Code, Codex, OpenCode and Google Antigravity sessions in a vim-ish style
Run with no arguments for the interactive menu; press / there to search, v to open the view options (normal/raw mode, message and section kinds) and Enter to view in vim.

In the normal viewer, `⟦meta⟧` marks generated headings, labels, diagnostics and log metadata (including reasoning summaries). `⟦local⟧` marks Claude's local structured tool details, which can differ from the model-visible result. Message and request text is left unchanged. Request roles follow the API: a `user` message can contain tool results or injected context. Tool calls are labelled as assistant output and results as tool output.

Claude, Codex and OpenCode support normal and raw views. Normal mode offers agent-specific section checkboxes with explanations. On Claude's API body messages row, type a number directly (`-1` = all, `0` = none); Backspace edits it. Raw mode contains only recoverable model-input text and its `⟦meta⟧` annotations, with no type-selection menu. It excludes usage/rate-limit records, runtime events, duplicate event copies, images and encrypted data. Claude unions reconstructed API request messages, displaying each message occurrence once with its `[number]`; resending a request prefix updates metadata rather than repeating bodies. Identical separate user prompts remain separate messages.

Codex/OpenCode do not log complete API requests: their raw views conservatively include explicit user/developer/system input records where available and tool-result text followed by a recorded model continuation. Generated replies, reasoning summaries and system/log notes are retained in normal mode; they are not guessed to be resubmitted input. Both modes use the same input projection. The full normal view includes every raw text and its source/count metadata, supplementing its usual sections where necessary; explicit normal-mode type filters still apply.

Fold summaries align both counts, timestamps, `[number]`, message/group labels and the start of summary text. `用户累加` counts user additions; `所有累加` includes automatic tool-result continuations. Both start at zero. Request stages progress `0/0` → `1/1` on the next user addition → `1/2` on an automatic continuation. A deduplicated Claude message shows the latest request stage in which it was sent; identical retries do not increment counts. Codex/OpenCode counts are inferred from recorded prompts, tool-result batches and response boundaries. Fold text displays the header directly to preserve alignment across nesting depths.

Raw opens directly on individual message folds, without an outer fold enclosing the entire view. Source labels distinguish real user text, tool results, injected context and compaction summaries even when their API role is `user`; mixed-source API messages are labelled `mixed`. User counters exclude recognized injected/synthetic context.

Requires Python 3.10+

# Changes from the repo-local helpers

The shared Python runtime replaced the Bash `codex-ephemeral.sh`/`codex-watch.sh`
pair under the same names. Every break a migrating caller must handle:

- Stdout carries only the `CODEX_RUN_START {json}` and `CODEX_RUN_EXIT {json}`
  lines. The Codex transcript and `tokens used` footer are in
  `<run>/provider.stdout`; the final message is `result.txt` or `--out`.
  `grep bwrap:` and marker extraction now read those files, not the log.
- `CODEX_RUN_EXIT rc=N` and `WATCHDOG: heartbeat`/`DIED` lines are gone; `rc=`
  substring parsers break. Read `exit_code`/`status` from the receipt. No
  detached watchdog exists; `--no-watchdog` is a no-op.
- `--json` JSONL lands in `provider.stdout`, not on stdout.
- The watcher exits 10 for a live run (`RUNNING`/`QUIET`) instead of 0, so
  `codex-watch.sh out.txt || recover` fires on every live run; `STALLED` is
  now `QUIET`; logs with only legacy `pid=` markers are refused (`UNKNOWN`).
- `--out` must not pre-exist (exit 2). Retries need a fresh path; the old `-o`
  overwrite is gone. The published file is mode 0600 rather than umask-based.
- `-- ""` falls back to stdin only when stdin is not a terminal.
- `sandbox_workspace_write.network_access=false` is always emitted unless
  `--network`, overriding a config that enables it; `--no-search` also emits
  `web_search="disabled"`.
- An empty final message is exit 4 `MISSING`, never a silent success.
- `ps` is required; native Windows/Git Bash is rejected (the old script ran
  under Git Bash).
- New: `--timeout`, `--preflight-timeout`, `--companion`, `--cli`, `--keep`;
  7-day retention sweep of finished run directories.

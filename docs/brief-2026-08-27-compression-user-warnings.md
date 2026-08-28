# Compression must warn before pausing a chat

## Observed failure

On 2026-08-27, Slack session `20260827_144456_abae013a` entered Codex app-server compression at 15:39:43 HST and made no visible progress for 4 minutes 20 seconds. During that interval, Ian sent more work. Slack showed no compression message, no reaction, and no queue acknowledgment, so the channel appeared dead and Ian used `/new` and reconstructed the handoff.

The compression lifecycle already emits routine start/done statuses, and `compression.progress_notices: true` already allows those statuses through the chat noise filter. Ian’s configuration now has that flag enabled. The current start text is too late and too vague, and there is no advance warning before the threshold is crossed.

## Governing rule and source

Ian’s required chat contract is:

1. Before automatic compression is required, send exactly: `:mega: Compression coming soon!`
2. At the moment automatic compression begins, send: `Pause! We are compressing at {time}`

For Ian’s Slack surface, `{time}` must be the current Hawaii time rendered like `3:42 PM HST` (12-hour clock, no leading zero).

Existing lifecycle/status owners:

- `agent/context_engine.py::automatic_compaction_status_message`
- `agent/conversation_compression.py::compress_context`
- `agent/turn_context.py` and `agent/conversation_loop.py` automatic threshold checks
- `gateway/run.py::_prepare_gateway_status_message`
- `tests/gateway/test_compression_progress_notices.py`

Reuse the existing status callback and `compression.progress_notices` gate. Do not create a second Slack send path.

## Behavior contract

### Advance warning

- For automatic compression only, emit `:mega: Compression coming soon!` once when the best available request/prompt usage first enters the warning band: at least 90% of `threshold_tokens`, but still below `threshold_tokens`.
- The warning must be emitted early enough that it can reach the chat before the synchronous compression call begins.
- Emit it at most once per compression cycle. Repeated tool/API turns within the band must not repeat it.
- Reset the latch after a successful compression boundary and on a real session reset.
- If one turn jumps from below the warning band directly to compression, emit `:mega: Compression coming soon!` immediately before the pause status, preserving that order. Do not skip the warning merely because the band was crossed in one jump.
- Do not warn when automatic compression is disabled, the engine has no usable threshold, or compression progress notices are disabled for chat delivery.

### Compression start

- Replace the routine automatic start text delivered to chat with `Pause! We are compressing at 3:42 PM HST` using the actual current Hawaii time.
- Keep manual `/compress` feedback and unrelated operational warnings unchanged.
- Keep the existing completion edge so the visible pause has a terminal state.
- The formatter must be deterministic under a pinned clock and portable across Linux, macOS, and Windows; do not depend on platform-specific `strftime` flags.

### Delivery and safety

- The warning and start statuses must use the existing gateway status callback/filter path and honor `compression.progress_notices`.
- Preserve existing noise suppression for auxiliary failures, retries, rate limits, and non-compression statuses.
- Preserve queue order, session history, prompt caching, compression thresholds, compression algorithm, app-server timeout behavior, and `/new` semantics.
- A failure to render or deliver a notice must never block compression or corrupt a turn.

## Acceptance tests

Use strict TDD: write each focused test first and show it failing for the missing behavior before production changes.

1. At 89.9% of the compression threshold, no advance warning is emitted.
2. On first entry at 90%–99.9%, exactly `:mega: Compression coming soon!` is emitted once.
3. Additional turns in the warning band do not repeat it.
4. Successful compression resets the latch so a later cycle can warn once again.
5. Session reset clears the latch.
6. A direct jump from below 90% to compression emits the warning before the pause status.
7. With a pinned Hawaii clock, automatic start text is exactly `Pause! We are compressing at 3:42 PM HST`.
8. The enabled chat gate delivers both new routine statuses on Slack, Telegram, Discord, and WhatsApp; the default/disabled gate suppresses them exactly as today.
9. Non-compression noise remains suppressed when progress notices are enabled.
10. Manual `/compress`, plugin engines that suppress automatic status, and programmatic/raw platforms retain their existing behavior.

Run the smallest focused agent tests plus:

```sh
scripts/run_tests.sh tests/gateway/test_compression_progress_notices.py
scripts/run_tests.sh tests/gateway/test_telegram_noise_filter.py
```

Also run any focused context-engine/conversation-loop test file changed by the implementation.

## Scope and review

- **Risk tier:** Tier 2 — customer-visible gateway behavior confined to compression/status reporting.
- **Expected owner files:** the existing compression lifecycle/threshold owner, `gateway/run.py` only if the filter’s scoped routine-status matcher needs updating, and focused tests.
- **Added-line budget:** 180 lines total across production and tests, excluding this brief. Stop and report if the clean implementation cannot fit.
- **Out of scope:** compression algorithms, thresholds, model/provider selection, retry or timeout policy, queue persistence, reactions, session reset, heartbeat behavior, config defaults, unrelated status wording, and refactors.
- Reuse existing helpers and follow file style. Comments explain why, not the next line.
- Handle only the observed automatic-compression lifecycle. Do not add speculative defenses.
- Check `git diff --stat` partway through and stop if size or scope no longer matches.
- Do not spawn reviewers or redesign the feature.
- Do not merge, deploy, restart the gateway, or call production.

## Proof and handoff

Return the failing RED command/output, GREEN focused test output, final diff stat, changed files, and any real blocker. The supervising agent will independently run tests and perform the Tier 2 review. A result of “already fine” is acceptable only if the exact user-visible contract above is proven through current behavioral tests.

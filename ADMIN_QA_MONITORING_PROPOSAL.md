# Admin Q&A Monitoring Redesign

Goal: make `/admin/qa` a surveillance-grade view of how users interact with the videos they downloaded—who is watching what, when, and which transcript slices they touch—so admins can spot abuse, heavy usage, or product friction quickly.

## Current gaps
- Feed only shows paged Q&A text; no obvious link to the specific videos or segments referenced.
- No filters for user/video/time/flags, so you cannot focus on one download or suspect user.
- No event-level telemetry (downloads, playbacks, exports) to correlate with Q&A.

## Monitoring data model
- Reuse `UsageEvent` with new `event_type` values: `video_download`, `video_play`, `video_seek`, `qa_asked`, `qa_answered`, `transcript_export`.
- Standard metadata per event: `user_id`, `video_id`, `conversation_id`, `message_id` (when applicable), `segment_start/end`, `client` (web/app), `ip_hash`, `user_agent`, `collection_id`, `had_flag`.
- Emit events at:
  - Download/export endpoints (`video_download`, `transcript_export`) including file size delivered.
  - Video player interactions (`video_play`, `video_seek`) with timestamps and playback position.
  - Chat events (`qa_asked`, `qa_answered`) including chunk IDs and token counts already available on `Message`/`MessageChunkReference`.

## Backend surface
- Extend `GET /admin/qa-feed`:
  - Filters: `video_id`, `user_email_or_id`, `answered` (true/false), `has_flags` (non-empty moderation flags), `min_latency_ms`, `start`, `end`.
  - Response enrichment: `source_videos` array per item `{video_id, video_title, first_timestamp, last_timestamp, snippet}` for quick video attribution; `latency_bucket` for coarse grouping.
- New endpoints:
  - `GET /admin/qa/summary` → counts for last 24h/7d (questions, flagged answers, avg latency, avg cost, downloads, playbacks) plus top 5 videos/users by activity.
  - `GET /admin/videos/{id}/usage` → timeline of `UsageEvent`s + QA rows for that video, optionally grouped by user.
  - `POST /telemetry/video-usage` (auth’d) → ingestion for player/download events so frontend/mobile can report plays/seeks.

## Admin UI redesign for `/admin/qa`
- Header metrics: active watchers (24h), downloads (24h), flagged answers, worst latency, top video by touches.
- Filter bar: search across question+answer text, user email/ID, video (typeahead against admin videos), date range presets (24h/7d/30d/custom), toggles for flagged-only and unanswered.
- Feed table upgrades:
  - Source chips showing video title + timestamp range; hovering reveals snippet; badge when multiple videos are stitched.
  - Cost + token column stays, add latency badge color-coded by SLA.
  - Row tags for `downloads-before-answer`, `high-risk-user`, `PII` if flags include `pii_detected`.
- Detail drawer on row click:
  - Full Q/A text, all flags, latency chart vs historical, token/cost breakdown.
  - Video evidence: list of source videos with jump URLs, segment ranges, and a mini “what the user watched” sparkline from `video_play/seek` events.
  - Conversation context: last 5 messages and quota status for that user.
- Alternate views:
  - “Video watchlist” tab: per-video cards (downloads, questions, flagged answers, top users, heatmap of timestamps hit).
  - “User sessions” tab: timeline of a user’s downloads/plays/questions to spot scraping patterns.

## Rollout plan
1) **Instrumentation first (backend)**: add new `UsageEvent` types + ingestion endpoint; extend QA feed filters and enrich response with `source_videos`.
2) **Feed UX upgrades (frontend)**: new filter bar + source chips + detail drawer; reuse existing API plus new fields.
3) **Video/user-centric views**: add watchlist and session timelines backed by `GET /admin/videos/{id}/usage` and summary endpoint.
4) **Alerting**: optional thresholds (e.g., >N plays or flagged answers per hour) to surface in `/admin/alerts`.

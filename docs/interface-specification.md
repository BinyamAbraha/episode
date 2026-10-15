# Interface specification

Investigation layout: persistent compact navigation, episode table, inspector with two camera panels, common timeline/cursor, playback and seek, state/action plots and accessible numeric sample table, findings with explanations, provenance, review and interval annotation forms. Secondary views: quality queue, selections, versions/comparison, jobs and verification.

Tokens: background #f3f4f0, surface #ffffff, text #172b2a, muted #4c605d, border #c8d1cb, accent #116457, danger #a52b35, warning #805300. System sans typography, tabular numbers, spacing 4/8/12/16/24/32 px, corners 3 px. Use color with text labels. No decorative metrics or gradients.

Desktop uses aligned split panels; narrow screens stack without document overflow. Tables scroll inside labelled regions. All forms have labels, errors, keyboard focus and pending/disabled feedback. Data loads show loading and explicit failures; empty catalogs show import action; interrupted jobs offer retry. Reduced motion disables animation. URLs retain episode and time. Charts supplement numeric alternatives.

Analysis appears below the primary inspector. The latest model run is selected when available; older runs remain selectable. Each suggestion shows evidence thumbnails, original interval and pending/reviewed status. Accept/edit/reject requires a reason; approved label/interval are shown separately from the original hypothesis. Diagnostic tables have keyboard-scrollable regions and numeric alternatives. Long provenance identifiers wrap on narrow layouts. Failed model validation exposes an error and raw output, with no actionable suggestions. Recorded replay analysis is read-only and explicitly unverified.

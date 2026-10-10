# Portfolio And Articles Site Concept

## Concept

Portfolio and articles site with an interactive competency matrix and an engineering case study.
Documents technical decisions through Clean Architecture, API-first backend design, and a modern DevOps stack.

## Audience

- Colleagues and like-minded people in IT
- Readers looking for practical engineering notes
- The author as maintainer of the portfolio and article archive

## Non-goals (will not build)

- Paid features. All functionality will be free.
- Complex role/permission system. Keep only guests, regular users, moderators for content
  authoring, administrators for moderator management, and a single owner for full team governance.
- Complex third-party integrations (CRM, ERP, etc.).
- Complex notification systems (email, SMS, etc.). A subscription to new articles, competency matrix updates, and new course releases is fine — nothing beyond that. No spam, mass mailings, or promo.
- Mobile app. The site will be responsive and mobile-friendly, but there will be no separate native app.
- Gamification. No points, levels, or achievements. Focus is on learning and skill development, not game mechanics. Progress tracking at most.
- Social features. No comments, follows, or feeds. Focus is on content and learning, not social interaction.
- Complex analytics. Basic user behavior analytics are fine — nothing beyond that.
- Content personalization. Content is the same for all users, regardless of preferences or history.

## Risks

- Content may grow uncontrollably. The site could become overloaded with content, making navigation and search harder.
- Keeping content up to date. Articles and the competency matrix require regular updates, which can be time-consuming.

## Core features

1. **Competency matrix** — localized interactive Q&A with normalized sheet/section/subsection taxonomy, topic filtering, detailed answers, and linked resources
2. **Articles** — localized content, folders, tags, search/filtering, and publish visibility
3. **Protected admin content workspace** — content management lives in `/admin-panel`, while public article and matrix pages stay read-only
4. **Privacy-safe analytics** — public article counters and anonymous reactions, period reports for articles and matrix questions, and anonymous daily public-site audience.

## Highlights

- Clean Architecture and best practices
- Interactive competency matrix with a database-backed taxonomy
- Infrastructure nginx kept as an edge reverse proxy for public routing and TLS

## Goal

Public portfolio for IT colleagues and readers, plus an article archive and engineering notebook for continued development.


## Anonymous analytics contracts

`competency-trainer` owns public-site traffic and matrix-reading aggregates; identity remains in
`auth-api`. `POST /api/analytics/visits` accepts only finite public-page categories or published
matrix targets (`sheetKey/slug`). Administrative reports live at `/api/admin/analytics/report`
and require moderator access. The report has an inclusive UTC date range of at most 1,096 days,
with optional source, content, folder/sheet, section and literal-title filters. Reports stay uncached.

Site and question views use random visit tokens for retry deduplication. Engagement requires an
existing view, is counted once, and keeps that view's source. The browser sends it after 15 seconds
in a visible tab; article reading retains its existing 30-second threshold. New article requests
send the browser's coarse source category. Older article engagement remains unattributed.

For visits, only daily aggregates persist long term. Receipts contain an HMAC scoped to the UTC day and target,
never raw tokens, IPs, account identifiers, user-agent strings, referrer URLs or query strings.
Receipts older than the previous UTC day are pruned on ingestion. Browser tokens rotate daily;
persistent local storage uses existing consent, otherwise session storage or memory is used.
The new site and matrix events exclude Do Not Track and content-manager visits at both browser
and API boundaries.

The site audience is an anonymous estimate of browsers per UTC day (sessions when persistence is
unavailable), not verified people. A month sums browser-days, not unique monthly users. Source
attribution for audience uses the browser's first tracked public visit that day. Article reaction
activity counts actual additions, replacements and withdrawals, separately from the public current
reaction totals. Reaction activity is unattributed and starts at deployment; no historical reaction
activity is fabricated. Individual queue submissions retain anonymous daily counts by sheet after
moderation/deletion; bulk queue imports do not count as user submissions. Structure labels in reports
follow the current content taxonomy. Deleted content retains anonymous counters under its identifier.

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
4. **Privacy-safe article analytics** — public counters and anonymous reactions

## Highlights

- Clean Architecture and best practices
- Interactive competency matrix with a database-backed taxonomy
- Infrastructure nginx kept as an edge reverse proxy for public routing and TLS

## Goal

Public portfolio for IT colleagues and readers, plus an article archive and engineering notebook for continued development.

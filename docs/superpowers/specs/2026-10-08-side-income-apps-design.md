# Side-Income Apps Portfolio — Design

**Date:** 2026-10-08
**Status:** Approved (design presented in chat; user approved the two-product set 2026-10-08)

## 1. Purpose

Earn **$100–500/month** of side income by building and selling small applications, working evenings/weekends (~5–10 h/week) with a preference for near-passive, low-maintenance products. This document designs the product portfolio, marketplaces, marketing strategy, and cost analysis. It is grounded in October 2026 marketplace and indie-income research (sources in §11).

## 2. Constraints

| Constraint | Value |
|---|---|
| Income target | $100–500/month (success = reaching this band within ~18 months) |
| Time | Evenings/weekends; near-passive after build |
| Upfront budget | ≤ $100 one-time |
| Maintenance | Light: bug fixes + a few marketing hours/week |
| Tech | Chosen by earning potential, not existing Python skills |

## 3. Strategy

Research findings that shape this design:

- **The $100–500/mo band is a top-25–35% outcome.** Median app earns ~$72/mo a year after launch; 26–54% of published products earn $0. Mitigation: a **small portfolio** — most apps make $50–200/mo, one or two carry the curve.
- **Winners in this band are narrow, search-driven tools** — small one-time-purchase utilities found via SEO/app-store search, not broad consumer apps, not AI wrappers, not generic productivity apps.
- **The only marketing channels that pay while you sleep are SEO and app-store search (ASO).** Reddit/communities work for launch pushes; paid ads and social video are poor ROI at 5–10 h/week.
- **Local-market arbitrage:** the owner (Polish-speaking, knows Allegro, KSeF, JPK) can produce Polish-language products and SEO that global indie devs cannot; Polish niches have a fraction of English-market competition.
- **Merchant-of-record (MoR) platforms remove all VAT administration** — a large hidden cost avoided (important for an EU/Poland-based seller).

**Portfolio (user-approved set):**

1. **SEO web micro-tool** — free client-side tool + one-time Pro unlock. Fastest path to first sale; most passive.
2. **Chrome extension for Allegro sellers** — Polish-language freemium extension. Cheapest entry ($5); passive store-search discovery.

*(A third candidate — a KSeF e-invoicing Shopify app — was proposed and deliberately dropped by the user to keep support load low.)*

**Build order:** micro-tool first (fastest cash, funds nothing but morale and learnings), extension second. The two cross-promote via a shared domain.

## 4. Product 1: SEO Web Micro-Tool

### 4.1 Shape & Pricing

A free, client-side tool (runs fully in the browser, no server, no marginal cost) built around a specific long-tail search demand. Paid **Pro unlock: one-time $19–29** sold as a license key via Lemon Squeezy.

Pricing rationale: sub-$10 products convert markedly worse (research found the $30–49 band is 35% of Gumroad revenue and converts 28% better than sub-$10); $19–29 sits at the bottom of the strong-converting range while staying impulse-buy friendly for a small utility. One-time licenses match the low-support goal and keep refunds and support minimal compared to subscriptions.

### 4.2 Niche Selection (implementation step 1)

Chosen by keyword research, not taste. Criteria: long-tail keywords with real search volume and weak competition; tool solves a specific, nameable task.

Seed candidates to research first:

1. **Creator utility** — subtitle/chapter/description tools for video creators. The fastest documented case in the research went $0 → $500/mo in 6 months on exactly this shape (60% of traffic from long-tail SEO).
2. **Developer micro-tool** — timestamp/JSON/encoding utilities. Crowded category; only viable with a genuine long-tail angle.
3. **Small-business doc generator** — e.g., a locale-specific invoice/receipt generator (a bridge toward local-market arbitrage).

Go/no-go: if keyword research finds no keyword with meaningful volume and a weak first page of search results, pivot to the next seed candidate.

### 4.3 Architecture & Marketplace

- **Hosting:** static HTML/JS on **Cloudflare Pages** (free tier, unlimited bandwidth, free SSL). No server, no database, no monthly cost.
- **Sales:** **Lemon Squeezy** (MoR): 5% + 50¢ per transaction; $50 minimum payout, paid out twice monthly; **Lemon Squeezy collects and remits EU VAT on your behalf** — no VAT MOSS/OSS registration for these sales. Caveat: Stripe acquired Lemon Squeezy (2024) and began steering toward Stripe Managed Payments in 2026; Lemon Squeezy remains live with unchanged pricing — revisit if it changes.
- **License check:** license key entered in the tool, validated against Lemon Squeezy's license API (client-side check is acceptable for this price point).
- **Domain:** one shared domain (~$12/yr), subpath or subdomain per product.

### 4.4 Marketing Strategy

1. **Long-tail SEO (primary, passive).** Programmatic content pages around the tool's keywords ("X vs Y", "how to do X", "X generator"); free micro-tools as link magnets. In the research data this channel drives 24% of first signups and compounds with zero ongoing cost.
2. **Reddit/communities (launch, active).** 3–4 weeks of genuine answering in relevant subreddits before ever mentioning the product; one 1,200-word value post in the case studies drove 1,100 visits / 31 signups. Reddit is the #1 first-signup channel (34%) but self-promotion gets removed/blacklisted — genuine help only.
3. **Directories (backlinks, one-time).** Submit to Uneed and MicroLaunch (2–4 hours total). Expect dozens–hundreds of visitors; the value is backlinks for SEO.
4. **Hacker News** if the tool ends up dev-audience: one Show HN attempt after community validation.
5. **Not doing:** paid ads (worst documented ROI), X/Twitter building-in-public as a primary channel (10% of signups), TikTok/YouTube (incompatible with 5–10 h/week).

### 4.5 Cost Analysis

| Item | Upfront | Recurring |
|---|---|---|
| Domain | ~$12 | ~$12/yr |
| Cloudflare Pages | $0 | $0 |
| Lemon Squeezy | $0 | 5% + 50¢ per sale |
| **Total** | **~$12** | **$12/yr + per-sale fees** |

### 4.6 Timeline & Expectations

- Build: 2–4 weeks of evenings.
- First sale: ~2–4 months (requires the SEO to start indexing/ranking).
- $100/mo: ~6–9 months.
- $100–500/mo: ~12 months (the fast case in research hit $500/mo at month 6, SEO-led).

### 4.7 Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Keyword doesn't rank | Ship 2–3 micro-tools, not one; go/no-go gate in 4.2 |
| Copycats | Move fast; SEO moat (ranked pages) compounds |
| License-key friction | One-time license, generous free tier |

## 5. Product 2: Chrome Extension for Allegro Sellers

### 5.1 Shape & Pricing

A Manifest V3 extension solving one specific Allegro-seller workflow. **Polish-language UI and Chrome Web Store listing** (the arbitrage: global devs don't serve this market well). Free tier + **one-time Pro unlock at 49–99 PLN**, sold via Lemon Squeezy license key (Chrome Web Store has no built-in payments since 2021).

### 5.2 Niche Selection (implementation step 1)

Selection method (proven pattern from research): enumerate existing Allegro extensions on the Chrome Web Store; mine 1–2★ reviews for recurring complaints; pick the workflow with the clearest unmet need and an abandoned/weak incumbent.

Candidate workflows: relisting assistant, repricing tool, dashboard analytics. Avoid saturated generic categories (tab managers, screenshot tools, AI sidebars).

Go/no-go: if review mining finds no complaint pattern, pivot to another workflow or micro-vertical (e.g., a different Polish marketplace).

### 5.3 Architecture & Marketplace

- **Distribution:** **Chrome Web Store** — $5 one-time developer registration; ~65% of installs come from store search (free passive ASO). Reality check: 91.5% of extensions have under 1,000 users — visibility comes from search, not the store's front page.
- **Sales:** Lemon Squeezy (as in 4.3 — MoR, VAT handled).
- **Tech:** JS/TS, MV3, local license-key check against the Lemon Squeezy API. Keep the scope tight (one workflow) — Allegro UI changes are the main maintenance cost.

### 5.4 Marketing Strategy

1. **Polish ASO (primary, passive).** Store listing optimized for Polish search terms sellers actually type; screenshots in Polish.
2. **Allegro-seller Facebook groups (launch).** The largest PL seller communities; the Reddit playbook applies — genuine help first, product mention after reputation.
3. **Official Allegro forum + Wykop** (launch, secondary).
4. **Cross-promotion from Product 1's domain** (Polish SEO pages about selling on Allegro).
5. **Not doing:** paid ads, PL YouTube tutorials (only if the extension proves itself and time allows).

### 5.5 Cost Analysis

| Item | Upfront | Recurring |
|---|---|---|
| Chrome Web Store registration | $5 one-time | — |
| Lemon Squeezy | $0 | 5% + 50¢ per sale |
| **Total** | **$5** | **per-sale fees only** |

### 5.6 Timeline & Expectations

- Build: 3–6 weeks of evenings.
- First sales: ~1–3 months after listing.
- $100–300/mo: ~6–12 months (successful solo extensions median $300–800/mo in year 1, but the median over all extensions is near zero — niche selection is everything).

### 5.7 Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Niche miss (nobody searches for it) | Review-mining selection method; go/no-go gate in 5.2 |
| Allegro UI changes break the extension | Tight scope, one workflow, quick bug-fix releases |
| Churn (one-time price, one-time customers) | Polish market size caps this risk; add new features as paid upgrades later |

## 6. Shared Infrastructure

- **One Lemon Squeezy account** for both products (single dashboard, one VAT arrangement).
- **One domain** (~$12/yr): product 1 on the root/subdomain, Polish SEO pages for product 2 alongside.
- **Cross-promotion:** product 1's pages link product 2 where audiences overlap (creators who sell physical goods on Allegro).

## 7. Financial Plan

### 7.1 Upfront & Recurring Costs (combined)

| Item | Upfront | Recurring |
|---|---|---|
| Domain | ~$12 | ~$12/yr |
| Chrome Web Store | $5 | — |
| Cloudflare Pages | $0 | $0 |
| Lemon Squeezy | $0 | 5% + 50¢ per sale |
| **Total** | **~$17** | **~$12/yr + per-sale fees** |

Well under the $100 budget; the rest is a buffer (e.g., a second domain, paid keyword tool tier if needed).

### 7.2 Income Projection (honest)

| Period | Expected range | Notes |
|---|---|---|
| Months 0–3 | $0 | Building + first listings + SEO indexing |
| Months 3–6 | $20–100/mo | First sales, both products live |
| Months 6–12 | $100–300/mo | SEO compounds; extension reviews accumulate |
| Months 12–18 | $100–500/mo | The target band |

Probability framing from the research: this trajectory is a **top 25–35% outcome**. 26–54% of published products never earn; the median earning product makes ~$72–170/mo. The two-product portfolio is the mitigation, not a guarantee. Expect to iterate or pivot one of the two products.

## 8. Tax (Poland)

- **VAT:** Lemon Squeezy is the merchant of record for both products — it collects and remits EU VAT. No VAT-OSS registration is required for these sales.
- **Income tax:** payouts are income; report per Polish rules. **Verify the exact form (ryczałt vs. skala) with an accountant before the first payout.**
- If either product later moves to direct sales (own Stripe), VAT obligations change — out of scope for now.

## 9. Work Plan (sequencing)

1. **Product 1, step 1:** keyword research for the seed candidates (§4.2). Decide or pivot. (~1–2 weeks)
2. **Product 1, step 2:** build free tool + Pro tier + Lemon Squeezy setup. (~2–4 weeks)
3. **Product 1, step 3:** launch: SEO pages, Reddit presence, directory listings. (ongoing)
4. **Product 2, step 1:** Chrome Web Store competitor review-mining (§5.2). Decide or pivot. (~1 week)
5. **Product 2, step 2:** build extension + listing + Lemon Squeezy license tier. (~3–6 weeks)
6. **Product 2, step 3:** launch: Polish ASO, FB groups, forum. (ongoing)

Each product gets its own design/spec before implementation begins (the standard workflow used in this repo).

## 10. Success Criteria & Checkpoints

- **At 3 months after a product's launch:** if it has earned $0, reassess — improve marketing, pivot, or drop it rather than keep polishing.
- **At 12 months:** portfolio at $100+/mo combined = on track; $500/mo = ahead of plan.
- **At 18 months:** portfolio in the $100–500/mo band = the goal achieved.

## 11. Key Research Sources

- [RevenueCat State of Subscription Apps 2026](https://www.revenuecat.com/sosa-26-insights/) — 17% of new subscription apps reach $1K MRR in 2 years; median ~$72/mo at year 1.
- [Gumroad 146K-product analysis](https://dev.to/solobillions/i-analyzed-146k-gumroad-products-heres-what-actually-makes-money-5e8i) — 44% earn $0; median $364 lifetime; $30–49 band = 35% of revenue.
- [Ask HN: $500/mo side projects (2026)](https://althacker.news/item?id=49417766) — real products in the band; portfolio patterns.
- [YouTube-tool case study](https://dev.to/nuco_z_270906fb0e460592db/from-side-project-to-500month-building-a-youtube-tool-as-a-solo-developer-8ok) — $500/mo in 6 months via long-tail SEO.
- [ProductWatch: first-100-users channel data](https://productwatch.io/blogs/how-indie-hackers-are-getting-their-first-100-users-in-2026) — Reddit 34%, programmatic SEO 24%, directories 12%, X 10%.
- [Chrome Web Store registration](https://developer.chrome.com/docs/webstore/register) — $5 one-time; [CWS payments deprecation](https://developer.chrome.com/docs/webstore/cws-payments-deprecation).
- [Lemon Squeezy pricing](https://www.lemonsqueezy.com/pricing) and [getting paid](https://docs.lemonsqueezy.com/help/getting-started/getting-paid) — 5% + 50¢, $50 min payout, twice monthly.
- [chrome-stats.com](https://chrome-stats.com/chrome/stats) — ~270K extensions; 91.5% under 1,000 users.

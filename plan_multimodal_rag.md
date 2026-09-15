# 🚀 Ship Apps Faster: Ideation to Production — The Complete Playbook

> A step-by-step blueprint for going from a raw idea to a live, production-grade application at maximum velocity using modern AI-augmented workflows.

---

## Table of Contents

1. [Phase 1 — Ideation & Problem Discovery](#phase-1--ideation--problem-discovery)
2. [Phase 2 — Validation & Scoping](#phase-2--validation--scoping)
3. [Phase 3 — Design & Architecture](#phase-3--design--architecture)
4. [Phase 4 — Environment & Toolchain Setup](#phase-4--environment--toolchain-setup)
5. [Phase 5 — Rapid Prototyping (MVP Build)](#phase-5--rapid-prototyping-mvp-build)
6. [Phase 6 — Core Development](#phase-6--core-development)
7. [Phase 7 — Testing & Quality Assurance](#phase-7--testing--quality-assurance)
8. [Phase 8 — CI/CD & DevOps Pipeline](#phase-8--cicd--devops-pipeline)
9. [Phase 9 — Pre-Launch & Staging](#phase-9--pre-launch--staging)
10. [Phase 10 — Production Deployment](#phase-10--production-deployment)
11. [Phase 11 — Post-Launch Monitoring & Iteration](#phase-11--post-launch-monitoring--iteration)
12. [Appendix — AI Tools & Resources](#appendix--ai-tools--resources)

---

## Phase 1 — Ideation & Problem Discovery

**Goal:** Clearly define *what* you're building and *why* it matters.

### Step 1.1 — Identify the Problem

- Write down the core problem in **one sentence** (the "elevator pitch").
- Ask yourself: *Who has this problem? How painful is it? How are they solving it today?*
- Use AI chatbots (ChatGPT, Claude, Gemini) to brainstorm variations of your idea and stress-test assumptions.

### Step 1.2 — Research the Landscape

- Search for existing solutions, competitors, and open-source alternatives.
- Use AI to summarize competitor features, pricing models, and user reviews.
- Identify the **gap** — what's missing or broken in current solutions.

### Step 1.3 — Define Your Unique Value Proposition (UVP)

- Distill what makes your app different into a single, compelling statement.
- Template: *"For [target user], who [has this problem], [App Name] is a [category] that [key benefit]. Unlike [competitors], we [differentiator]."*

### Step 1.4 — Capture the Idea Document

- Create a lightweight **Product Brief** (1–2 pages max) covering:
  - Problem statement
  - Target audience / user personas
  - Core use cases (top 3–5)
  - Success metrics (what does "winning" look like?)
  - Non-goals (what you are explicitly NOT building)

**⚡ AI Accelerator:** Use an AI assistant to generate the first draft of your product brief from a single paragraph description. Refine from there instead of starting from a blank page.

---

## Phase 2 — Validation & Scoping

**Goal:** Prove the idea has legs *before* you write a single line of code.

### Step 2.1 — Validate Demand

- **Talk to real users:** Conduct 5–10 short interviews (15–20 min each). Ask about their current workflow, pain points, and willingness to pay/use a new tool.
- **Landing page test:** Spin up a quick landing page (use AI site builders like v0, Bolt, or Lovable) describing the product. Add a waitlist signup. Drive traffic via social media or communities. Measure signup conversion.
- **Community signals:** Post about the concept in relevant Reddit, Discord, X (Twitter), or Hacker News communities. Gauge reactions.

### Step 2.2 — Define the MVP Scope

- List **all** features you can imagine.
- Ruthlessly prioritize using the **MoSCoW method**:
  - **Must Have** — Without these, the app is useless.
  - **Should Have** — Important, but launch can survive without them.
  - **Could Have** — Nice to have; build only if time permits.
  - **Won't Have (this time)** — Explicitly deferred to v2+.
- Your MVP = **Must Haves only**. Everything else is a distraction.

### Step 2.3 — Write User Stories

- For each Must Have feature, write user stories:
  - *"As a [user type], I want to [action] so that [benefit]."*
- Attach acceptance criteria to each story (clear definition of "done").
- Use AI to generate initial user stories from your feature list, then refine them.

### Step 2.4 — Create a Rough Timeline

- Estimate effort for each user story (T-shirt sizing: S / M / L / XL).
- Map stories to weekly sprints.
- Set a hard **launch deadline** (ideally 2–6 weeks for an MVP).

**⚡ AI Accelerator:** Use AI to generate user stories, estimate complexity, and even suggest which features to cut to hit your deadline.

---

## Phase 3 — Design & Architecture

**Goal:** Establish the visual identity, user experience, and technical foundation.

### Step 3.1 — UX/UI Design

- **Wireframes first:** Sketch low-fidelity wireframes for every screen (pen & paper or tools like Excalidraw, Figma).
- **AI-assisted design:** Use tools like v0 (Vercel), Galileo AI, or Figma AI to generate UI component designs from text descriptions.
- **Design system:** Pick an existing component library (shadcn/ui, Tailwind UI, Material UI, Chakra UI) instead of designing from scratch. This alone saves weeks.
- **User flow mapping:** Document the critical paths (signup → onboarding → core action → value delivery).

### Step 3.2 — Choose Your Tech Stack

Pick technologies that optimize for **speed of development** and **ecosystem maturity**:

| Layer | Recommended Options | Why |
|-------|-------------------|-----|
| **Frontend** | Next.js, Nuxt, SvelteKit, React + Vite | Full-stack frameworks with built-in routing, SSR, and deployment |
| **Styling** | Tailwind CSS + shadcn/ui | Utility-first, AI-friendly, copy-paste components |
| **Backend/API** | Next.js API Routes, FastAPI, Express, Hono | Minimal boilerplate, fast iteration |
| **Database** | PostgreSQL (via Supabase/Neon), SQLite (via Turso), MongoDB | Managed services = zero ops overhead |
| **Auth** | Clerk, NextAuth, Supabase Auth, Firebase Auth | Don't build auth from scratch — ever |
| **Payments** | Stripe, Lemon Squeezy | Battle-tested, well-documented |
| **Hosting** | Vercel, Railway, Fly.io, AWS Amplify | Git-push deploys, auto-scaling |
| **AI/LLM Integration** | OpenAI API, Anthropic API, LangChain, Vercel AI SDK | If your app has AI features |

### Step 3.3 — System Architecture Design

- Draw a high-level architecture diagram (use AI or Excalidraw):
  - Client → API Gateway → Services → Database
  - External integrations (auth, payments, email, storage)
- Decide on architectural patterns:
  - **Monolith** (recommended for MVPs — simpler, faster to ship)
  - **Modular monolith** (if you anticipate needing to break out services later)
  - Microservices (almost never appropriate for an MVP)
- Define your data model:
  - Core entities and relationships
  - Use AI to generate the initial schema from your user stories

### Step 3.4 — API Design

- Define your API contract early (REST or tRPC or GraphQL).
- Document endpoints, request/response shapes, and error codes.
- Use AI to generate OpenAPI specs from natural language descriptions.

**⚡ AI Accelerator:** Describe your app to an AI assistant and ask it to generate the complete database schema, API routes, and architecture diagram. Use this as a starting point, not the final answer.

---

## Phase 4 — Environment & Toolchain Setup

**Goal:** Get a fully functional development environment running in under an hour.

### Step 4.1 — Repository Setup

```bash
# Initialize the project
mkdir my-app && cd my-app
git init

# Use a starter template (saves hours)
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir
# OR
npx create-t3-app@latest
# OR
npm create vite@latest
```

- Set up the Git repository with a clear branching strategy:
  - `main` — production-ready code only
  - `develop` — integration branch
  - `feature/*` — individual features

### Step 4.2 — AI-Powered Development Environment

- **Cursor IDE** — Your primary development environment. Configure it with:
  - Project-specific rules (`.cursor/rules/`) for consistent AI-assisted coding
  - Custom context about your project architecture
  - Relevant MCP servers for your workflow
- **AI Coding Assistants** — Use Cursor's built-in agent mode for:
  - Generating boilerplate code
  - Writing tests
  - Debugging errors
  - Refactoring code
  - Code reviews via Bugbot

### Step 4.3 — Essential Tooling

- **Package manager:** pnpm (faster, stricter) or npm
- **Linting/Formatting:** ESLint + Prettier (configure once, forget forever)
- **Type safety:** TypeScript in strict mode (catches bugs before runtime)
- **Pre-commit hooks:** Husky + lint-staged (enforce quality on every commit)
- **Environment variables:** `.env.local` + a `.env.example` template

### Step 4.4 — Third-Party Service Setup

- Create accounts and get API keys for:
  - Database provider (Supabase, Neon, PlanetScale)
  - Auth provider (Clerk, Supabase Auth)
  - Payment processor (Stripe)
  - Email service (Resend, SendGrid)
  - File storage (S3, Cloudflare R2, Supabase Storage)
  - Error tracking (Sentry)
  - Analytics (PostHog, Mixpanel)
- Store all keys securely in `.env.local`.

**⚡ AI Accelerator:** Ask your AI assistant to generate the entire project scaffolding, configuration files, and even the initial database migration based on your schema design.

---

## Phase 5 — Rapid Prototyping (MVP Build)

**Goal:** Get a working end-to-end prototype as fast as humanly possible.

### Step 5.1 — Build the Critical Path First

- Identify the **single most important user flow** (the one that delivers core value).
- Build it end-to-end: UI → API → Database → back to UI.
- Ignore edge cases, error handling, and polish. Just make it *work*.
- This should take **1–3 days max**.

### Step 5.2 — AI-Powered Code Generation Workflow

Follow this loop for maximum velocity:

```
1. Describe the feature in natural language to your AI assistant
2. Review the generated code — understand what it does
3. Test it immediately in the browser/app
4. Fix issues by describing them to the AI
5. Commit working code frequently (small, atomic commits)
6. Repeat
```

**Key principles:**
- **Don't write boilerplate manually.** Let AI generate CRUD operations, form handling, API routes, database queries, and component scaffolding.
- **Do understand every line.** AI generates; you validate. Never ship code you don't understand.
- **Iterate in small chunks.** Build one feature at a time. Get it working before moving on.

### Step 5.3 — Tackle Features in Priority Order

Work through your Must Have features sequentially:

1. **Authentication** — Sign up, sign in, sign out, protected routes
2. **Core data model** — Create, read, update, delete for your primary entities
3. **Core workflow** — The main thing users come to do
4. **Basic navigation** — App shell, routing, layout
5. **Essential integrations** — Payments, email notifications, etc.

### Step 5.4 — Use Pre-Built Solutions Aggressively

- Don't build what you can buy/borrow:
  - Auth → Clerk / Supabase Auth (not custom JWT logic)
  - Payments → Stripe Checkout (not custom payment forms)
  - Email → Resend templates (not custom email rendering)
  - File uploads → Uploadthing / S3 presigned URLs
  - Real-time → Supabase Realtime / Pusher
- Every hour spent building commodity features is an hour stolen from your unique value.

**⚡ AI Accelerator:** Use Cursor's agent mode to generate entire feature modules. For example: *"Create a complete CRUD API and UI for managing projects, including a list view, detail view, create form, and delete confirmation dialog using shadcn/ui components and server actions."*

---

## Phase 6 — Core Development

**Goal:** Build out the full MVP feature set with reasonable quality.

### Step 6.1 — Establish Development Rhythm

- **Daily cadence:**
  - Morning: Review what's left, pick the highest-priority task
  - Build: Focus blocks of 2–4 hours of uninterrupted coding
  - Evening: Commit, push, review progress against timeline
- **Weekly check-ins (if team):**
  - Demo what's built
  - Adjust priorities based on learnings
  - Update timeline if needed

### Step 6.2 — Frontend Development

- Build reusable component library early (buttons, inputs, modals, cards, tables).
- Implement responsive design from the start (mobile-first).
- Handle loading states, empty states, and error states for every view.
- Use optimistic UI updates for better perceived performance.
- Implement proper form validation (client-side + server-side).

### Step 6.3 — Backend Development

- Implement business logic in service layers (separate from route handlers).
- Add input validation on all API endpoints (Zod, Valibot).
- Implement proper error handling with consistent error response format.
- Add rate limiting on public endpoints.
- Set up database migrations (Drizzle, Prisma, or raw SQL migrations).

### Step 6.4 — Data Layer

- Implement efficient database queries (avoid N+1 problems).
- Add database indexes for frequently queried fields.
- Set up proper relationships and foreign keys.
- Implement soft deletes where appropriate.
- Add created_at / updated_at timestamps to all tables.

### Step 6.5 — Security Essentials (Non-Negotiable)

Even for an MVP, these are **not optional**:

- [ ] Authentication on all protected routes
- [ ] Authorization checks (users can only access their own data)
- [ ] Input sanitization (prevent XSS, SQL injection)
- [ ] HTTPS everywhere
- [ ] Secure session management
- [ ] Environment variables for all secrets (never hardcode)
- [ ] CORS configuration
- [ ] Rate limiting on auth endpoints

### Step 6.6 — Performance Basics

- Implement pagination for all list views.
- Add caching where it makes sense (Redis, in-memory, or HTTP cache headers).
- Optimize images (next/image, WebP format, lazy loading).
- Code splitting / lazy loading for large pages.
- Database connection pooling.

**⚡ AI Accelerator:** Use AI for code reviews on every PR. Ask it to check for security vulnerabilities, performance issues, and bugs. Use Cursor's Bugbot for automated code review.

---

## Phase 7 — Testing & Quality Assurance

**Goal:** Ensure the app works reliably without spending weeks on test suites.

### Step 7.1 — Testing Strategy for Speed

Don't aim for 100% coverage on an MVP. Focus testing effort where it matters most:

| Test Type | What to Test | Tools | Priority |
|-----------|-------------|-------|----------|
| **Smoke Tests** | Critical user paths work end-to-end | Playwright, Cypress | 🔴 High |
| **Integration Tests** | API endpoints return correct data | Vitest, Jest, Supertest | 🔴 High |
| **Unit Tests** | Complex business logic, utilities | Vitest, Jest | 🟡 Medium |
| **Type Checking** | Entire codebase compiles | TypeScript compiler | 🔴 High |
| **Linting** | Code quality and consistency | ESLint | 🔴 High |

### Step 7.2 — AI-Assisted Test Writing

- Use AI to generate test cases from your code:
  - *"Write integration tests for the /api/projects endpoint covering success, validation errors, auth failures, and not-found cases."*
- Use AI to generate test data and fixtures.
- Use AI to identify edge cases you might have missed.

### Step 7.3 — Manual QA Checklist

Before shipping, manually verify:

- [ ] Signup / Login / Logout flow works
- [ ] Core workflow completes successfully
- [ ] Payment flow processes correctly (use Stripe test mode)
- [ ] Email notifications are sent and received
- [ ] Mobile responsiveness is acceptable
- [ ] Error messages are user-friendly
- [ ] Loading states render properly
- [ ] Empty states are handled gracefully
- [ ] Browser back/forward buttons work correctly
- [ ] Deep links / URL sharing works

### Step 7.4 — Cross-Browser & Device Testing

- Test on Chrome, Firefox, and Safari (minimum).
- Test on a real mobile device (not just browser DevTools responsive mode).
- Test on slow network (Chrome DevTools → Network → Slow 3G).

**⚡ AI Accelerator:** Generate your entire test suite using AI. Describe the feature behavior and let the AI write the tests. You review, adjust, and run them.

---

## Phase 8 — CI/CD & DevOps Pipeline

**Goal:** Automate the path from code commit to production deployment.

### Step 8.1 — Continuous Integration (CI)

Set up GitHub Actions (or equivalent) to run on every push/PR:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check
      - run: npm run test
      - run: npm run build
```

### Step 8.2 — Continuous Deployment (CD)

- **Vercel / Netlify / Railway:** Connect your Git repo. Every push to `main` auto-deploys to production. Every PR gets a preview deployment.
- **Docker-based (if needed):**
  - Write a Dockerfile
  - Build and push to a container registry
  - Deploy to your hosting platform

### Step 8.3 — Branch Protection

- Require CI to pass before merging to `main`.
- Require at least one review (if you have a team).
- No direct pushes to `main` — all changes go through PRs.

### Step 8.4 — Environment Management

Set up three environments:

| Environment | Purpose | URL | Deploy Trigger |
|------------|---------|-----|----------------|
| **Development** | Local dev | localhost:3000 | N/A |
| **Staging** | Pre-production testing | staging.yourapp.com | Push to `develop` |
| **Production** | Live users | yourapp.com | Push to `main` |

**⚡ AI Accelerator:** Use AI to generate your entire CI/CD pipeline, Dockerfile, and deployment configuration from a description of your stack.

---

## Phase 9 — Pre-Launch & Staging

**Goal:** Final preparation before going live.

### Step 9.1 — Staging Deployment & Verification

- Deploy the complete app to a staging environment.
- Run through the entire user journey end-to-end on staging.
- Test with real (but test) data — not lorem ipsum.
- Verify all integrations work in the staging environment (Stripe test mode, email delivery, file uploads).

### Step 9.2 — Performance Audit

- Run Lighthouse audit (aim for 90+ on Performance, Accessibility, Best Practices).
- Test page load times on 3G network.
- Check for memory leaks (long-running sessions).
- Verify database query performance under simulated load.

### Step 9.3 — Security Audit

- Run automated security scan (Snyk, npm audit).
- Review all environment variables are properly set in production.
- Verify no secrets are committed to the repository.
- Check CORS, CSP headers, and HTTPS enforcement.
- Test auth flows for vulnerabilities (broken access control, session hijacking).

### Step 9.4 — Legal & Compliance

- [ ] Privacy Policy page
- [ ] Terms of Service page
- [ ] Cookie consent banner (if serving EU users / GDPR)
- [ ] Data processing agreements with third parties (if applicable)
- [ ] Accessibility compliance (WCAG 2.1 AA minimum)

### Step 9.5 — Launch Prep

- [ ] Domain name purchased and DNS configured
- [ ] SSL certificate active
- [ ] Transactional emails configured (welcome, reset password, receipts)
- [ ] Error tracking active (Sentry)
- [ ] Analytics installed (PostHog, Mixpanel, or Google Analytics)
- [ ] Uptime monitoring configured (BetterUptime, Checkly)
- [ ] Backup strategy for database
- [ ] On-call plan for the first 48 hours post-launch

**⚡ AI Accelerator:** Use AI to generate your privacy policy, terms of service, and cookie consent implementation. Use AI security review tools to audit your codebase.

---

## Phase 10 — Production Deployment

**Goal:** Ship it. For real. To real users.

### Step 10.1 — The Deployment

```bash
# If using Vercel (simplest path)
git checkout main
git merge develop
git push origin main
# Vercel auto-deploys. Done.

# If using Docker / custom hosting
docker build -t myapp:latest .
docker push registry.example.com/myapp:latest
# Trigger deployment via CD pipeline
```

### Step 10.2 — Post-Deployment Verification

Immediately after deploying:

1. **Smoke test production:** Sign up with a new account, complete the core flow.
2. **Check error tracking:** Monitor Sentry for any new errors (first 30 minutes are critical).
3. **Check analytics:** Verify events are being tracked.
4. **Check performance:** Load the app on mobile — does it feel snappy?
5. **Check email delivery:** Trigger a test email and verify it arrives (check spam folder).
6. **Check payments:** Process a test transaction (Stripe live mode with a real card, then refund).

### Step 10.3 — Launch Announcement

- Share on your channels: X/Twitter, LinkedIn, Product Hunt, Hacker News, Reddit, IndieHackers.
- Email your waitlist (if you built one during validation).
- Personal outreach to your interview subjects from Phase 2.
- Consider a Product Hunt launch for maximum initial visibility.

### Step 10.4 — First 48 Hours Protocol

- Monitor error rates continuously.
- Respond to user feedback within hours, not days.
- Fix critical bugs immediately (have a fast hotfix process).
- Document all feedback — every piece is gold at this stage.

---

## Phase 11 — Post-Launch Monitoring & Iteration

**Goal:** Learn, improve, and grow.

### Step 11.1 — Monitoring & Observability

Set up dashboards for:

- **Application health:** Error rates, response times, uptime (Sentry, BetterUptime)
- **User analytics:** Signups, activation, retention, feature usage (PostHog, Mixpanel)
- **Business metrics:** Revenue, churn, conversion rates (Stripe Dashboard, custom dashboards)
- **Infrastructure:** CPU, memory, database connections, costs (hosting provider dashboard)

### Step 11.2 — Feedback Collection

- Add an in-app feedback widget (Canny, UserVoice, or a simple form).
- Conduct follow-up interviews with early users.
- Monitor support channels (email, Discord, Twitter mentions).
- Track feature requests and categorize them.

### Step 11.3 — Iteration Cycle

Enter a fast iteration loop:

```
Week 1-2 post-launch:
  → Fix bugs and critical UX issues
  → Improve onboarding based on user behavior data

Week 3-4:
  → Ship the top-requested "Should Have" feature
  → Optimize performance bottlenecks
  → A/B test key conversion points

Monthly:
  → Review metrics against success criteria
  → Reprioritize roadmap based on data
  → Consider "Could Have" features
  → Evaluate scaling needs
```

### Step 11.4 — Scaling Decisions

When you start seeing traction, address:

- **Database scaling:** Read replicas, connection pooling, query optimization
- **Application scaling:** Horizontal scaling, CDN for static assets, edge computing
- **Team scaling:** When to hire, what roles to fill first
- **Architecture scaling:** When to break the monolith (hint: later than you think)

---

## Appendix — AI Tools & Resources

### AI-Powered Development Tools

| Category | Tool | Use Case |
|----------|------|----------|
| **IDE & Code Generation** | Cursor | AI-first IDE; agent mode for full feature generation |
| **UI Generation** | v0 (Vercel) | Generate React/Next.js UI from text prompts |
| **Full App Generation** | Bolt, Lovable, Replit Agent | Generate and deploy full apps from descriptions |
| **Design** | Figma AI, Galileo AI | AI-assisted UI/UX design |
| **Database** | Supabase AI, Drizzle Studio | AI-assisted schema design and query building |
| **Testing** | Cursor + Vitest | AI-generated test suites |
| **Documentation** | AI Assistants | Generate README, API docs, user guides |
| **Code Review** | Cursor Bugbot | Automated code review on PRs |
| **DevOps** | AI Assistants | Generate CI/CD configs, Dockerfiles, IaC |

### Speed Multipliers (Biggest Time Saves)

1. **Use a framework with conventions** (Next.js, Rails, Laravel) — don't make decisions the framework has already made.
2. **Use a component library** (shadcn/ui) — don't design buttons from scratch.
3. **Use managed services** (Supabase, Clerk, Stripe) — don't build commodity infrastructure.
4. **Use AI for boilerplate** — let AI write the repetitive code; you write the unique logic.
5. **Use templates and starters** — start from a proven foundation, not an empty folder.
6. **Deploy from day one** — push to production on day 1 with a "Hello World." Deploying should never be a surprise.
7. **Cut scope ruthlessly** — the fastest code to ship is the code you don't write.

### Anti-Patterns to Avoid

| ❌ Don't | ✅ Do Instead |
|----------|--------------|
| Build custom auth | Use Clerk, Supabase Auth, or NextAuth |
| Design from scratch | Use shadcn/ui + Tailwind |
| Over-engineer the database | Start simple, normalize later |
| Write microservices for MVP | Build a monolith, extract later |
| Spend weeks on CI/CD | Use Vercel's git-push deploy |
| Aim for 100% test coverage | Test critical paths, ship fast |
| Premature optimization | Profile first, then optimize bottlenecks |
| Build in isolation for months | Ship weekly, get feedback constantly |
| Bike-shed on tech stack | Pick proven tools, start building |
| Ignore errors and logs | Set up Sentry + monitoring from day 1 |

---

## Timeline Summary

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Ideation & Validation | 3–5 days | Product brief + validated demand |
| Design & Architecture | 2–3 days | Wireframes + tech stack + schema |
| Environment Setup | 0.5–1 day | Repo + tooling + services ready |
| MVP Build (Prototype) | 1–2 weeks | Core flow working end-to-end |
| Core Development | 1–3 weeks | Full MVP feature set complete |
| Testing & QA | 2–3 days | Critical paths tested, bugs fixed |
| CI/CD & DevOps | 0.5–1 day | Automated pipeline running |
| Pre-Launch | 1–2 days | Staging verified, legal pages done |
| Production Deployment | 1 day | App is LIVE 🎉 |
| Post-Launch Iteration | Ongoing | Continuous improvement |

**Total estimated time to production: 4–8 weeks** (solo developer or small team with AI tools)

---

*"If you're not embarrassed by the first version of your product, you've launched too late." — Reid Hoffman*

*Ship fast. Learn fast. Iterate fast. The market rewards speed.*

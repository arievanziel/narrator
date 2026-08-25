# V2-10 — Polish & Launch Readiness

**Status:** Planning — no implementation yet
**Priority:** Final step before v2 release
**Estimated effort:** Medium-Large
**Feedback:** Add `>` inline notes anywhere.

## Summary

The final subversion: polish everything, optimize performance, make it mobile-friendly, deploy to production, and prepare for public launch.

## Performance

### Generation latency

**Target:** From the moment the reader sends an action to the first audio playing, the delay should be under 3 seconds.

**Current:** LLM call (2-5s) + TTS generation (1-3s for first segment) = 3-8s

**Optimizations:**
- **Streaming LLM:** Use streaming API calls so the first tokens arrive while the LLM is still generating. Parse sections as they arrive. Start TTS for the first segment before the LLM finishes.
- **Parallel TTS:** Generate multiple segments in parallel (already partially done via the audio queue).
- **Pre-generation:** Pre-generate choice audio (already done). Also pre-generate likely next-scene ambience.
- **Caching:** Cache TTS for common phrases (e.g., "You decide to..."). Cache music tracks.
- **Model selection:** Use faster models for simple passages, smarter models for complex ones.

### Audio pipeline

- **Buffer management:** Ensure smooth playback without gaps between segments
- **Preloading:** Preload the next segment while the current one plays
- **Memory:** Clean up old audio files to prevent disk bloat
- **Queue depth:** Optimal queue depth — not too deep (wastes resources) or too shallow (causes gaps)

### Frontend performance

- **Rendering:** Large stories (50+ passages) should render smoothly
- **Virtual scrolling:** Only render visible passages, lazy-load others
- **Asset loading:** Minimize CSS/JS size, consider bundling
- **Caching:** Service worker for offline capability (PWA)

## Mobile responsiveness

### Design

The book GUI should work beautifully on:
- Desktop (1920px+, 1440px, 1280px)
- Tablet (768px, 1024px) — portrait and landscape
- Phone (375px, 414px) — portrait primary

**Layout changes for mobile:**
- Top bar: simplified (title only, controls in a menu)
- Side panels: become full-screen overlays on mobile (slide in from left/right)
- Story area: full width, larger text option
- Audio bar: simplified (play/pause, progress, time)
- Input: full-width input at the bottom, above the audio bar

**Touch interactions:**
- Tap to toggle panels
- Swipe left/right to open/close panels
- Swipe up/down to scroll story
- Long-press a passage for options (replay, copy, share)

### PWA (Progressive Web App)

- Installable on mobile home screen
- Works offline (service worker caches the app shell)
- Background audio playback (media session API)
- Push notifications (optional: "Your narrator has a new chapter ready")

**Implementation:**
- `manifest.json` for PWA metadata
- Service worker for offline caching
- Media session API for background audio controls (lock screen controls)
- Apple touch icon and splash screen

## Deployment

### Hosting options

**Option A: Self-hosted VPS**
- A single VPS (DigitalOcean, Hetzner, Linode) running the Python server
- Nginx reverse proxy for HTTPS
- Simple, inexpensive, full control
- Scales to ~50-100 concurrent users per VPS

**Option B: Containerized (Docker)**
- Docker container with the app
- Deploy on Fly.io, Railway, or Google Cloud Run
- Auto-scaling, easy deploys
- Better for growth

**Option C: Serverless**
- Not ideal for Narrator because of long-running TTS generation
- Could work with a queue-based architecture (separate workers for TTS)

**Recommendation:** Option B (Docker on Fly.io or Railway) for ease of deployment and scaling.

### CI/CD

- GitHub Actions for automated testing on every push
- Auto-deploy on merge to main
- Health check endpoint (`/api/health`)
- Rollback on failed deploy

### Monitoring

- Error tracking: Sentry
- Uptime monitoring: UptimeRobot or Better Uptime
- Performance monitoring: custom metrics endpoint
- Log aggregation: if using the logging system from v1.2

## Polish

### Visual polish

- **Typography:** Fine-tune font sizes, line heights, and spacing for optimal reading
- **Themes:** Ensure light, sepia, and dark themes are all beautiful
- **Animations:** Smooth transitions between passages, chapter openings, panel toggles
- **Loading states:** Elegant loading indicators (not spinners — maybe a "The narrator is turning the page..." message)
- **Error states:** Friendly error messages that stay in the book metaphor

### UX polish

- **Onboarding:** First-time user experience — a brief tutorial or guided tour
- **Tooltips:** Helpful tooltips on first use of each feature
- **Keyboard shortcuts:** Enter to send, 1-9 for choices, space for play/pause, etc.
- **Accessibility:** Screen reader support, keyboard navigation, high contrast mode
- **Settings persistence:** All settings saved to localStorage (already done for some)

### Content polish

- **System prompt refinement:** The system prompt is the soul of the narrator. Spend time refining it for quality, consistency, and literary tone.
- **Golden tests:** Expand golden tests to cover more scenarios and ensure quality doesn't regress.
- **Edge cases:** Handle very long stories (100+ passages), very short stories (1-2 passages), stories with no combat, stories with lots of dialogue.

## Launch checklist

- [ ] All v1.1-v1.9 features implemented and tested
- [ ] Full test suite passes (100+ tests)
- [ ] Playwright smoke test passes on desktop and mobile viewports
- [ ] No console errors
- [ ] No engine internals visible in book mode
- [ ] Audio works smoothly for 20+ passages
- [ ] Save/load works across sessions
- [ ] Library shows multiple stories correctly
- [ ] World view renders without errors
- [ ] Mobile layout tested on real devices
- [ ] PWA installable and works offline
- [ ] HTTPS configured
- [ ] Health check endpoint responds
- [ ] Error tracking configured
- [ ] Uptime monitoring configured
- [ ] Landing page or documentation for new users
- [ ] Privacy policy (if accounts are involved)
- [ ] Terms of service (if commercial)

## Post-launch (v2.1+ ideas)

- Multi-player shared steering
- Voice cloning
- AI-generated cover art
- Story marketplace
- Mobile native app (React Native / Flutter)
- Real-time collaboration (two readers steering together)
- Branching narratives (save at a fork, explore both paths)
- "Director's commentary" mode (the narrator explains its choices)
- Story analytics dashboard (word count, reading time, story arc visualization)
- Integration with e-book readers (Kindle, Kobo) via EPUB export
- Podcast mode (serialized delivery of new chapters)

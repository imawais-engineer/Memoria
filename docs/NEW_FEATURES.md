**Project:** Memoria – Self-Evolving Personal AI with Human-like Memory  
**Track:** 1 – MemoryAgent  
**Purpose:** Additional high-value features to increase user experience, innovation, and judge appeal.

---

## Feature Overview & Prioritization

These features enhance usability, personalization, and privacy while staying true to the MemoryAgent theme.

### Priority Order (Recommended Implementation)

### 1. Simple Authentication & User Onboarding (High Priority)

**Description:**
- Simple, judge-friendly login/signup (no email verification to avoid friction).
- Each user has a unique `username`.
- Core profile: First Name, Last Name, Username, Favorite Book (used as soft password).

**Implementation Details:**
- On signup: Check username uniqueness.
- On login: Ask for `username` + `favorite_book`.
- Store user profile in DB (new `users` table).
- All memories linked to `user_id`.

**Why it helps:**
- Enables true multi-user support.
- Makes demo more realistic.
- Improves scoring in Presentation & Impact.

---

### 2. Persistent Chat Sessions & History

**Description:**
- Chat history persists across refreshes, tab changes, and browser sessions.
- Sidebar with list of past chats (like ChatGPT/Grok).
- "New Chat" button.
- Click any past chat to resume.
- Delete Chat option (with warning).

**Key Behavior:**
- Deleting a chat → deletes all memories extracted from that specific chat (with confirmation).
- Regular memory deletion only affects individual memories.

**Scoring Impact:** Strong improvement in UX and real-world value.

---

### 3. Personal Intelligence (Global Memory Access)

**Description:**
- Toggleable feature: "Enable Personal Intelligence"
- When enabled → Agent has full access to **all** user memories across every chat.
- When disabled → Only memories from current chat + core memories are used.

**Default:** Enabled (with easy toggle in settings).

---

### 4. MemoryLess Mode (Incognito / Private Session)

**Description:**
- User can start a "MemoryLess" session (Incognito mode).
- In this mode:
  - No memory is read.
  - No new memories are created or updated.
  - Completely private conversation.
- Session ends (and is wiped) when user switches chat, refreshes, or closes tab.
- Clear warning modal when starting MemoryLess mode.

**Scoring Impact:** Excellent for Privacy & Innovation.

---

### 5. Persona Customization

**Description:**
- User can customize how the AI should behave.
- Options include:
  - Response Length (Concise / Balanced / Detailed)
  - Tone & Style (Professional, Friendly, Educational, Witty, etc.)
  - Behavior Traits (Cautious, Encouraging, Direct, etc.)
  - Include personal context (Name, Profession, Goals, etc.)

- Stored as part of user profile / core memory.
- Applied in system prompt.

**Scoring Impact:** Strong personalization & user control.

---

## Technical Implementation Notes

- Create new DB table: `users`
- Add `user_id` foreign key to all memories and chats.
- New table: `chat_sessions` (id, user_id, title, created_at, is_memoryless)
- New table or JSON field for user persona settings.
- Update all memory operations to respect current chat + user preferences (Personal Intelligence toggle).

---

## 5. Multimodal Generation & Model Switcher (Implemented)

**Description:**
- **Create tab** — generate images (`wan2.1-t2i-plus`) and videos (`wan2.1-t2v-turbo`) from prompts.
- Per-user quotas: default **5 images** and **2 videos** (stored on `users` table).
- Gallery of past generations via `GET /api/generate/assets`.
- **Chat model switcher** — pick `qwen-plus`, `qwen-max`, `qwq-plus`, or `qwen-turbo` per session.

**Why it helps:**
- Showcases full Qwen Cloud / DashScope stack beyond text chat.
- Quota limits keep demo costs predictable for judges.
- Model switcher demonstrates flexibility without breaking memory features.

---

## Next Steps

1. Implement **Feature 1 (Onboarding/Login)** first.
2. Then **Feature 2 (Chat History)**.
3. Then Privacy toggles (Personal Intelligence + MemoryLess).
4. Finally Persona Customization.

---

**Ready for Implementation**

Reply with **"Start Feature 1"** (Onboarding) and I will give you the full set of Cursor-ready prompts + DB migration steps.

This plan is clean, non-destructive to existing memory system, and significantly raises the project's polish and innovation score.

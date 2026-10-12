# AQREM UI interaction inventory

Status key: **Fixed** = verified by unit/E2E or manual wiring in this pass; **Partial** = improved but not full Rule 5 scope; **N/A** = static text or requires authenticated E2E.

| Screen | Element | Type | Before | After | Verification |
|--------|---------|------|--------|-------|--------------|
| App shell | Sidebar collapse | button | Toggle worked, weak focus | `aq-interactive`, Ctrl/Cmd+B, tooltips when collapsed | Build + shortcuts in AppShell |
| App shell | Command palette | dialog | Missing | Ctrl/Cmd+K, sidebar ⌘K, nav commands | E2E N/A (auth); manual wiring |
| App shell | Mobile sidebar backdrop | button | Closed sidebar | Same + aria-label | Static test |
| Sidebar | New chat | button | Worked | Unchanged + toast on delete elsewhere | Manual |
| Sidebar | Search conversations | input | Filter only | aria-label + conversation filter | Manual |
| Sidebar | ⌘K | button | Dead / missing | Opens command palette | Manual |
| Sidebar | Primary nav links | link | Routed | Active/hover tokens, review badge | NavLink |
| Sidebar | Conversation row menu | menu | Partial | Rename, share link toast, delete confirm | ConfirmDialog + toast |
| Sidebar | User footer | menu | Settings link | Sign out + settings | Manual |
| Sidebar | Sources nav | link | Was dead/wrong | Routes to `/sources` | Route exists |
| Chat header | Title dropdown | button | **Dead** (fake) | Static title text | Code review |
| Chat header | Share | button | No feedback | Copy link + toast | ChatConversationHeader |
| Chat header | Sidebar expand | button | Worked | IconButton + tooltip | Manual |
| Chat empty | Starter prompts | button | Fill composer | Unchanged | chatComposer tests |
| Chat scope | Project picker | control | Opens picker | Unchanged | Manual |
| Composer | Attach | button | Disabled w/o reason | Tooltip with reason, drag-drop | ChatComposer |
| Composer | Send / Stop | button | Partial states | Tooltips, loading, `aq-interactive` | chatComposer.test |
| Composer | `/` focus | shortcut | Missing | Focuses textarea when not typing | useKeyboardShortcuts |
| Messages | Needs review badge | link | Static tag | Links to `/review-queue` | MessageList |
| Messages | Copy / regen / feedback | buttons | Silent feedback | Toast on good/bad | ChatPage + toast |
| Messages | Scroll to bottom | button | Missing | Floating button when scrolled up | CSS + MessageList |
| Settings | Theme radios | radio | Instant apply | Toast on change | SettingsPage |
| Settings | Sign out | button | Worked | Clears session + navigate | SettingsPage |
| Settings | Copy email/org id | button | Missing | CopyButton + copied state | CopyButton |
| Activity | Search / sort / dates | inputs | Basic list | Filters, sort, date range | AuditLogPage |
| Activity | Export CSV | button | Missing/dead | Downloads CSV + toast | AuditLogPage |
| Activity | Row expand | button | Missing | Expand details + CopyButton on IDs | AuditLogPage |
| Login | Sign in | submit | Worked | Loading spinner text | E2E a11y |
| Login | Theme default | script | Light possible | `data-theme=dark` default | E2E dark/light |
| Dashboard | Cards/rows | mixed | Some slate hex | **Partial** — tokens not fully swept | Not in this pass |
| Projects | CRUD controls | mixed | Backend tied | **Partial** | Needs auth E2E |
| Review queue | Actions | mixed | Backend tied | **Partial** | Needs auth E2E |
| Admin consoles | Invites/tokens | forms | Prior invite fix on other branch | **Partial** | Backend tests elsewhere |

## Tests

| Suite | Command | Result |
|-------|---------|--------|
| Unit (Vitest) | `npm run test` | 42 passed — includes `interactiveControls.test.ts`, theme contrast |
| E2E (Playwright) | `npm run test:e2e` | 8 passed (login a11y, dark default, focus) dark + light projects |
| Build | `npm run build` | Pass |

## Gaps (honest)

- Full authenticated Playwright walk of every workspace route requires test credentials and API; not configured in CI here.
- Dashboard, Evidence, Questionnaires, Review Queue, Answer Library, and admin shells were not individually re-audited in browser this turn; sidebar/command palette routes exist.
- Settings save/dirty for org fields not implemented (read-only account section only).

## Changed files (this pass)

See git history on branch `cursor/chat-ui-intent-81ca` for UI components under `frontend/src/components/ui/`, chat/shell/pages updates, `frontend/e2e/*`, `frontend/src/test/interactiveControls.test.ts`, `docs/UI_INTERACTION_INVENTORY.md`.

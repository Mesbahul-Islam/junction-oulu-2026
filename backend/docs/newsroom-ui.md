# Newsroom dashboard

Job: let staff see what needs attention, follow agent work, and review content before publication.
Challenge criteria: meaningful human oversight, transparent agent operation, community accountability.

Data and behaviours retained: JWT and Google login; staff-only API; dashboard counts and scheduling;
manual runs, run selection and polling; desk outputs and story stages; ready-story publication;
editor/language queues, filtering, edits, checklists, approval/rejection/change requests and batch approval;
community moderation and linking answers; comparing up to three readers' personalized feeds.

Desktop (1024px and up):

    240px sidebar  | breadcrumb                         theme
    Kalevalo Admin| ----------------------------------------
    Workspace     | Overview                updated / refresh
    Overview      | Six compact metrics, divided by hairlines
    Editor queue  | ----------------------------------------
    Community     | Current shift / recent runs | AI models
    AI newsroom   |                             | human review
    Compare feeds | Wide database views for queue / run stories
    account       |

Mobile/tablet (below 1024px):

    menu   Newsroom / current view                  theme
    ----------------------------------------------------
    Page title / supporting text
    Metrics in two columns
    Shift and models stacked
    Filters wrap; tables scroll inside labelled regions
    Menu opens modal navigation drawer; Escape closes it

Kajo: exact light/dark HSL palette from frontend/src/styles/globals.css, Plex Sans/Arabic,
6px controls, 8px panels, ink selection/actions/focus. Provenance colours retain their meanings.
Loading, empty and error states live inside the relevant content region. Dialogs replace browser prompts.

Verification: backend serving/static assets and API contracts, JS syntax and interaction self-checks.
Browser screenshot verification is blocked when no CUA browser is connected.

## Settings tab

Job: understand the configuration actually used by the newsroom (agent viability and human oversight).
Read-only; no credential values are returned. Data comes from the staff-only dashboard endpoint.
Show the stored scheduler interval/enabled state, resolved models/endpoints, credential-presence flags,
RSS ingestion limits and deduplication, Jev ranking configuration, target languages and current review rules.
Desktop: sidebar | title + refresh | two-column settings panels, label/value rows.
Mobile/tablet: drawer | title + refresh | stacked panels with wrapping label/value rows.

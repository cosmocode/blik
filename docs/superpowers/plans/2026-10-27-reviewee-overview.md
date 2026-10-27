# Reviewee overview utility refresh

**Goal:** Help HR users find people, understand their feedback status, and take the next useful action without a row full of controls.

**Reference:** Read-only inspection of `.claude/worktrees/cycle-table-filters` found server-side name/email search, questionnaire filters, mutually exclusive stage counts, sorting, and query-preserving pagination. Adapt those ideas without modifying that worktree or its cycle view. The installed Django querystring tag already includes the question mark.

**Design:** Group name/email in one column; show Not started, In progress or Completed with cycle counts. Keep latest questionnaire visible by default. Offer optional Department and Self vs others columns through an accessible native popover, with local browser preferences. Explain the gap in plain language and reveal its column when sorting by gap. Use a context-sensitive primary action and overflow menu for secondary actions. Replace one-click quick-create/split buttons with a small questionnaire-selection dialog that explains copying previous reviewers and sending invitations.

**Constraints:** Preserve org scoping, active/GDPR exclusion, report anonymity thresholds, existing management permissions and confirmation routes. Keep UUID links and CSRF-protected quick creation. Choose an active default when the last questionnaire is archived. No changes to the cycle-filter worktree. Run app/tests only in Docker. Continue in the current workspace to retain the earlier design changes and Docker bind mount.

- [x] Add tests for scoped search, department/latest-questionnaire filters, status counts, invalid inputs, pagination/filter preservation, gap sorting/anonymity, archived questionnaire fallback, permissions and query growth.
- [x] Refactor only reviewee_list and its supporting constants in blik/admin_views.py, batch-load latest cycles/reports, and add filter context.
- [x] Replace reviewee_list.html; add scoped CSS/JS and a start-cycle dialog partial, using shared dashboard styles.
- [x] Translate new copy into both German variants.
- [x] Run relevant reviewee/UUID/quick-cycle/report-gap regressions, compile catalogs, inspect desktop/mobile/light/dark and keyboard flows in Docker, then request a focused review.

**Review focus:** Filters cover the full dataset before pagination; counts match search/questionnaire/department scope; optional columns remain usable with long text; active cycles can coexist with older reports; no new report/private-data access; menu/dialog keyboard focus and viewport bounds; start-cycle dialog makes email side effects visible and never auto-submits during verification.

**Verification:** The 81-test Docker regression run passed (reviewee overview, permissions, UUID routes, bulk cycles, cycle categories, report gaps and languages). Both German catalogs compiled. Browser checks covered search and status filters, saved column choices, gap-column disclosure, archived questionnaire fallback, desktop light/dark appearance, and a 390px mobile viewport. The mobile dialog fits between x=16 and x=374; Escape closes it and restores focus to the row's action trigger. No review-creation form was submitted during verification.

**Review finding resolved:** A focused independent review found that the shared popover resize handler passed Window to Node.contains(). Reproduced the exception, fixed the handlers in the reviewee and questionnaire pages, and confirmed resizing closes the popover successfully.

**Related user requests:** Enabled the existing bulk-cycle creation flag for the local admin@test.local preview account. Intermittent empty cycle lists came from old Gunicorn view/template state after the concurrent cycle-filter merge, rather than missing database rows. Before the fix, repeated browser refreshes alternated between zero and three rows; afterward, eight refreshes all showed three rows and the new filters. Added docker-compose.dev.yml and blik/settings_dev.py to run the auto-reloading development server inside Docker on localhost, retaining the same persistent PostgreSQL volume; documented the command in README.md. Production settings remain separate.

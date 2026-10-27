# Questionnaire table refresh implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this small presentation change.

**Goal:** Bring the questionnaires dashboard in line with the existing dashboard tables.

**Architecture:** Replace the individual questionnaire cards with the shared `card` / `card-body` / `table-wrapper` / `table` structure used by Reviewees and Review Cycles. Render active and archived rows through one template partial. Following the user's review, move descriptions and translation details into a native dialog opened from the questionnaire name, and secondary actions into an anchored native popover. Reuse existing buttons, badges, modal styles, help text, layout utilities, and theme colors.

**Tech stack:** Django templates, existing dashboard CSS, and small page-scoped JavaScript for native dialogs and popovers. No new dependencies. Run the application and checks in Docker as requested.

**Spec:** The user requests shared dashboard styles, then a less cramped overview with an ecommerce-style quick preview for nontechnical HR users. Remove the creation date. Show concise purpose descriptions and actual report capabilities with icons and plain labels (radar, Dreyfus skill, agency, answer breakdowns and written feedback). Preview all questions and answer options in a dialog without leaving the list, with language choice and an example-report link. Keep existing permissions, archive/delete confirmation, and CSRF-protected restore.

## Review focus

- Long questionnaire names/descriptions must wrap without stretching the page.
- Tables must scroll within their cards on mobile and remain keyboard accessible.
- Light/dark themes must use shared color tokens.
- Members must retain preview/report access without management controls.
- Empty and archived-only lists must remain useful; absent question counts should display zero.
- Dialogs and menus must open by keyboard, close with Escape, and restore focus; menus must escape the scrolling table's clipping and remain inside the viewport.
- Load question previews on demand through the existing organization-scoped preview route. Include loading, retry, cancellation, and normal full-page link fallback. Test authentication, organization isolation, language selection, all answer types, and escaping.
- Derive report indicators from current report behavior without extra database queries; do not advertise unavailable visuals. Translate new UI copy into both German variants.

## Task 1: Refresh the list presentation

- [x] Replace card-per-questionnaire markup in `templates/admin_dashboard/questionnaire_list.html` and introduce `templates/admin_dashboard/partials/questionnaire_table.html`.
- [x] Reuse existing shared styles; scope any additional layout rules to the questionnaire table.
- [x] Add `templates/admin_dashboard/partials/questionnaire_dialog.html`, keeping details accessible without expanding the overview rows.
- [x] Add `questionnaire_questions.html` and the preview fragment response; add focused preview tests before implementing it.
- [x] Add `questionnaires/presentation.py` capability descriptions and focused tests; connect the icons to the overview and explanatory dialog.
- [x] Run the existing questionnaire permission, archive/delete, translation, report-type, and UUID URL tests in the separate Docker test stack (118 tests, including the new preview and capability tests, passed).
- [x] Verify dialogs and action menus by keyboard and pointer in Docker; inspect desktop/mobile and light/dark appearances. At 390px the page and dialog stay within the viewport, all questions load, and the dialog body scrolls while controls remain visible.
- [x] Review the diff and run `git diff --check`.

**Verification:** Docker regression run passed 118 tests. German catalogs compiled successfully. Independent review prompted matching rating choices to the real form (1–5, including unlabelled values, plus “Did not observe”); the added regression passed. Browser checks confirmed all 27 sample questions load in place, switching to German updates questions and the full-preview link, and loading/error indicators are hidden after success. Dialog Escape restores focus and overflow links work by keyboard.

**Report column refinement:** Replace wrapping feature badges with one consistent icon strip and a “Report details” trigger. Show concise explanations and the example-report link in a native, keyboard-focusable popover, positioned beside the trigger when space allows. Use a simplified brilliant-cut gemstone for Skill level, referencing the Dreyfus diagram's Expert stage. German catalogs updated and compiled; the Docker regression run again passed all 118 tests. Review confirmed permissions and links are preserved. Browser checks verified dark/light styling, 390px viewport bounds, keyboard opening, focus into the panel, and Escape restoring focus.

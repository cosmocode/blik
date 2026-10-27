# Profile page refresh implementation plan

> Implement inline using the executing-plans skill, continuing the authorized dashboard design refresh in the existing Docker-bound workspace.

**Goal:** Make the profile page consistent with Blik's dashboard and easy to scan for nontechnical users.

**Architecture:** Replace obsolete Bootstrap layout utilities with shared cards, form controls, buttons and a responsive grid. Put editable personal details beside read-only account/organization information. Present personal feedback cycles in the shared table below. Keep the welcome guide accessible through a native dialog.

**Scope:** Presentation and form accessibility. Preserve existing organization filtering, profile saving, cycle/report access and translations. No dependencies, deployment or commits. Continue running the app and checks in Docker.

**Design choice:** A single page with grouped cards keeps the small form and report history discoverable; tabs would hide useful content and a full-width stacked form is the current problem. Username is plain read-only information. Use one clear save action. Move response-category detail behind a disclosure, avoiding badge clutter.

## Task 1: Refresh and verify the profile

- [x] Add focused regression coverage for saving, visible field errors, report access states, and organization isolation. First demonstrate the missing language validation error.
- [x] Rebuild `templates/accounts/profile.html`; extract a native welcome dialog into `templates/accounts/partials/welcome_guide.html`; reuse existing dashboard CSS tokens and components. Add language help text to `ProfileEditForm` so it is linked to its field.
- [x] Translate new copy into both German catalogs.
- [x] Run profile, account, language and report tests in Docker. Compile locales and check whitespace.
- [x] Check the actual page in Docker: desktop/mobile, light/dark, empty history, native dialog focus/Escape. Verify populated history and validation through rendered response tests. Request a focused independent review.

## Review focus

- Long account/email/questionnaire strings must wrap without stretching the page.
- Only completed cycles with reports retain the report link; other users' and organizations' cycles stay hidden.
- Every invalid field including language must show an accessible error without losing submitted values.
- Welcome guide must have a visible close control, Escape dismissal, focus restoration, and a mobile scrollable body.
- Preserve username as read-only and keep the CSRF-protected form wired to the same view.

**Follow-up:** User requested a narrower navigation language picker and corrected chevron alignment. The shared switcher retains its native select, full option names, CSRF and existing POST; navigation enables a compact selected-language label. CSS positions the chevron inside a dedicated wrapper with a visible keyboard focus ring. Other switcher instances keep full selected-language names.

**Verification so far:** 51 Docker tests pass (profile, accounts, language, report). The reviewer identified untranslated form labels; a German regression reproduced it, lazy translated labels fixed it, and both German variants now pass. Mobile profile/dialog remain within 390px; dialog body scrolls with the close button visible. Navigation widths are 59px for EN and 90px for DE (Du), with an 11px inset and vertically centered chevron. Language switching updates the page and profile as before.

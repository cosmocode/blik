# Slack app: cycle creation and reminders in DMs

Date: 2026-10-07
Status: approved in conversation, revision 1

## Goal

Let a Blik organization connect its Slack workspace so that review cycles can
be created from Slack and every reviewer-facing message (invitation,
self-assessment, reminder, report ready, ready to close) lands as a Slack DM
instead of an email whenever the recipient is in that workspace. Reviewers
who are not in Slack keep getting email, exactly as today.

Hosted customers first. The integration lives inside the Django project so
self-hosted installs get it too by registering their own Slack app.

Out of scope for this spec: hardening the public API or webhooks so that a
third party could build the same thing externally. The API has no
reviewer-slot endpoint, webhooks deliver once with no retries, and the
`send_reminders` API action is broken. Those are separate work items.

## Decisions already made

| Decision | Choice |
|---|---|
| Where the code lives | Inside the Django monolith, new `slack` app. No separate service. |
| Slack client | Stdlib `urllib.request` and `hmac`. No `slack_sdk`, no `requests`. |
| Identity resolution | By email, at request or send time. No table mapping Slack ids to anyone. |
| Workspace to org | One to one. |
| Cycle creation depth | Full modal in Slack, never leaves Slack. |
| Reminder cadence | Every 3 days, at most 3 reminders, both org-adjustable. Applies to email as well as Slack. |
| Channel choice | Slack DM when the email resolves to a workspace member, otherwise email. Never both. |
| Scheduler | Existing daily crontab in `docker-entrypoint.sh`. No Celery. |
| Post-submit work | `transaction.on_commit` plus a daemon thread, the pattern `api/webhooks.py` already uses. |

## Part 1: Slack app registration and install

### The Slack app itself

Blik owns one Slack app, created at api.slack.com in Blik's own workspace
(the "development workspace") with **Public Distribution** enabled under
Manage Distribution. Public distribution is not a Marketplace listing. It only
means any workspace may install via OAuth using Blik's client id and secret.
The app is not discoverable; installs happen from Blik's "Connect Slack"
button.

Two apps are registered: production, with request URLs on the hosted domain,
and development, with request URLs on a local tunnel. They are configured
identically otherwise.

Credentials come from env and are read in `blik/settings.py`:

```
SLACK_CLIENT_ID
SLACK_CLIENT_SECRET
SLACK_SIGNING_SECRET
```

When `SLACK_CLIENT_ID` is empty the "Connect Slack" button is hidden and
every other code path behaves as if no workspace is connected.

Self-hosters register their own app from `docs/slack-manifest.yaml`, swap in
their domain, and set the same three env vars. They do not need public
distribution because they install into one workspace.

**Bot scopes:** `commands`, `chat:write`, `users:read`, `users:read.email`,
`im:write`. No channel or message reading scopes.

**Request URLs** (all under `/slack/`):

| Path | Who calls it | Purpose |
|---|---|---|
| `install/` | Org admin (browser) | Redirect to Slack's authorize page |
| `oauth/callback/` | Slack redirects admin's browser | Exchange code, store workspace |
| `commands/` | Slack | The `/blik` slash command |
| `interactions/` | Slack | Modal submissions |

No Events API subscription, so no events endpoint.

### Install flow

1. An admin with `accounts.can_manage_organization` clicks "Connect Slack" on
   the organization settings page (`settings_view` in `blik/admin_views.py`,
   template `templates/admin_dashboard/settings.html`).
2. `install/` builds a `state` with `django.core.signing.dumps({"org": id,
   "user": id})` and redirects to `https://slack.com/oauth/v2/authorize` with
   the client id, the bot scopes, the redirect URI, and the state.
3. `oauth/callback/` verifies `state` with `signing.loads(max_age=600)`,
   refuses a mismatch with the logged-in user's org, exchanges `code` at
   `oauth.v2.access`, and writes a `SlackWorkspace` row. An existing row for
   the org is replaced (reinstall). Redirects back to settings with a success
   message.
4. "Disconnect" calls `auth.revoke` with the bot token (best effort, ignore
   failures) and deletes the row.

### Model

```python
class SlackWorkspace(TimeStampedModel):
    organization = OneToOneField(Organization, on_delete=CASCADE, related_name='slack_workspace')
    team_id = CharField(max_length=32, unique=True)
    team_name = CharField(max_length=255)
    bot_user_id = CharField(max_length=32)
    bot_token_encrypted = BinaryField()          # Fernet, same key and scheme as Organization.smtp_password
    installed_by = ForeignKey(User, null=True, on_delete=SET_NULL)
    is_active = BooleanField(default=True)
```

`bot_token` is a property with a setter, mirroring `Organization.smtp_password`.
`team_id` is unique so one workspace cannot be connected to two orgs.

### Request verification

Every request to `commands/` and `interactions/` is verified before parsing:

```
sig_basestring = f"v0:{X-Slack-Request-Timestamp}:{raw_body}"
expected = "v0=" + hmac.new(SLACK_SIGNING_SECRET, sig_basestring, sha256).hexdigest()
```

Reject with 401 when the timestamp is more than 300 seconds from now or
`hmac.compare_digest(expected, X-Slack-Signature)` is false. Both views are
`csrf_exempt`; the signature is the CSRF defence.

### Resolving people

Two directions, both by email, both without any stored mapping.

**Blik to Slack.** `users.lookupByEmail` with the email already on the
`ReviewerToken`, `Reviewee`, or `User`. A hit that is not deleted and not a
bot yields a user id for the DM. Anything else (not found, deactivated,
guest without email, API error) means fall back to email. The Slack user id
is used for the one `chat.postMessage` call and discarded.

**Slack to Blik.** A slash command or modal payload carries the caller's
Slack `user_id`. `users.info` yields `profile.email`. That email must match a
`User` whose `UserProfile.organization` is the workspace's org. No match
returns an ephemeral message: "Your Slack email {email} doesn't match a Blik
account in {org name}." Permission to create cycles is the same check
`review_cycle_create` makes in the web UI.

**Anonymity.** Nothing new links a Slack identity to review data. `Response`
already links to `ReviewerToken`, which already carries `reviewer_email`;
this spec adds no further linkage.

## Part 2: Cycle creation in Slack

### Slash command

`/blik` with no text, or `/blik new`, opens the create modal with
`views.open` on the payload's `trigger_id`. This is one API call and finishes
well inside Slack's 3-second acknowledgement window.

`/blik status` replies ephemerally with the caller's active cycles: reviewee
name, questionnaire, and `completed/total` tokens with emails. Cycles the
caller created, or all org cycles when the caller has
`can_view_all_reports`. Nothing else is recognised; unknown text gets a short
usage line.

### The modal

| Block id | Element | Required | Resolves to |
|---|---|---|---|
| `reviewee` | `users_select` | yes | Slack user, then `users.info`, then `Reviewee` matched by email in the org, or created with the Slack real name and that email |
| `questionnaire` | `static_select` | yes | Org's questionnaires, as the web create form lists them |
| `peers` | `multi_users_select` | no | One `peer` token per resolved email |
| `managers` | `multi_users_select` | no | One `manager` token per resolved email |
| `direct_reports` | `multi_users_select` | no | One `direct_report` token per resolved email |
| `external` | `plain_text_input`, multiline | no | Comma or newline separated emails, one `peer` token each |

One `self` token with the reviewee's email is always created.

`static_select` is capped at 100 options by Slack. An org with more than 100
questionnaires is not a case worth handling now.

### Submission handling (`interactions/`, `type == view_submission`)

1. Verify signature, identify the submitter (Part 1), check create
   permission. Failure is a modal-level error.
2. Resolve every selected Slack user to an email with `users.info`. A user
   with no email becomes a field error on the block that named them. Lowercase
   and deduplicate emails; drop the reviewee's own email from the reviewer
   lists. Validate external emails with Django's `validate_email`; bad ones
   are a field error on `external`.
3. In one `transaction.atomic()`:
   - `Reviewee.objects.get_or_create(organization=org, email=email,
     defaults={'name': real_name})`. Reactivate if `is_active` is false.
   - `ReviewCycle.objects.create(reviewee, questionnaire, created_by=user,
     status='active')`. `NoCycleCredits` becomes a field error on `reviewee`
     with the exception's message.
   - Create `ReviewerToken` rows with `reviewer_email` set directly, one per
     category and email, plus the self token. Token creation bypasses
     `assign_tokens_to_emails` because there are no pre-made empty tokens to
     shuffle; every token is born with its email.
4. Respond `{"response_action": "clear"}` so the modal closes.
5. `transaction.on_commit` starts a daemon thread that calls
   `send_reviewer_invitations(cycle)` and `send_reviewee_notifications(cycle)`
   (both now route through `deliver`, Part 3) and then DMs the creator a
   confirmation: reviewee, questionnaire, reviewer count per category, and a
   link to `review_cycle_detail`.

Field errors use Slack's `{"response_action": "errors", "errors": {block_id:
message}}` shape.

## Part 3: Delivery and reminders

### `deliver`

A single function in `slack/client.py`:

```python
def deliver(organization, email, *, subject, text, html, slack_text, slack_url, slack_button):
    """Slack DM when the org has a workspace and the email resolves, else email."""
```

Behaviour:

- No active `SlackWorkspace` for the org, or `lookupByEmail` misses: call
  `core.email.send_email(subject, text, [email], html_message=html)` exactly
  as the callers do today. Return `'email'`.
- Hit: `chat.postMessage` to the user id with `slack_text` as the fallback
  text and one `section` block plus one `actions` block holding a button
  labelled `slack_button` that opens `slack_url`. Return `'slack'`.
- Slack API failure after a successful lookup: fall back to email and log at
  warning. Never raise past the caller's existing error handling.

The three reviewer-facing paths in `reviews/services.py` replace their
`send_email` call with `deliver`:

| Function | Slack button |
|---|---|
| `send_reviewer_invitations` (reviewer and self branches) | "Give feedback" / "Start self-assessment" |
| `send_reminder_emails` | "Give feedback" |
| `send_reviewee_notifications` self-assessment part | "Start self-assessment" |

The `slack_text` for each is a two or three line mrkdwn rendering of the
same information the email carries. No new templates; the text is built in
`slack/blocks.py`.

### Other DMs

- **Report ready.** In the existing `report_generated` signal in
  `api/signals.py`, after the webhook, DM the cycle creator (`created_by`)
  with a "View report" button to the report. When
  `Organization.auto_send_report_email` is true the reviewee is notified
  through the existing report email path, which gains a `deliver` call like
  the others.
- **Ready to close.** `send_close_check_emails` keeps its seven-day,
  at-least-one-response rule and sends through `deliver`. It additionally
  sends the same message to `cycle.created_by` when that user has an email.
  `close_check_sent_at` still guards against repeats for both recipients.
- **Creation confirmation.** Part 2, step 5.

No per-submission notifications to the creator. `/blik status` covers
progress on demand.

### Reminder scheduler

New management command `send_reviewer_reminders` in
`slack/management/commands/`. A token is **due** when all of these hold:

1. `reviewer_email` is set
2. `invitation_sent_at` is set
3. `completed_at` is null
4. `cycle.status == 'active'`
5. `reminder_count < organization.reminder_max`
6. `coalesce(last_reminder_sent_at, invitation_sent_at) <= now - organization.reminder_interval_days`

Due tokens are grouped by cycle and passed to `send_reminder_emails(cycle,
token_ids=[...])`, which now goes through `deliver` and increments
`reminder_count` alongside `last_reminder_sent_at`. `--dry-run` prints the
due tokens and sends nothing.

The crontab line in `docker-entrypoint.sh` becomes:

```
0 9 * * * cd /app && export $(cat /app/.env.cron | xargs) && python manage.py send_cycle_reminders && python manage.py send_reviewer_reminders >> /var/log/cron.log 2>&1
```

The env grep on the line above it gains `SLACK_`.

**Behaviour change for existing orgs.** Automatic email reminders do not
exist today. After this ships every org, Slack-connected or not, reminds
reviewers every 3 days up to 3 times. `reminder_max = 0` turns it off for an
org. This is intended.

## Part 4: Schema, settings UI, files

### Migrations

- `slack/0001`: `SlackWorkspace`.
- `core/00xx`: `Organization.reminder_interval_days = PositiveSmallIntegerField(default=3)`,
  `Organization.reminder_max = PositiveSmallIntegerField(default=3)`.
- `reviews/00xx`: `ReviewerToken.reminder_count = PositiveSmallIntegerField(default=0)`.

### Settings page

`settings_view` and `templates/admin_dashboard/settings.html` gain:

- A "Slack" card. When `SLACK_CLIENT_ID` is set: either a "Connect Slack"
  button linking to `/slack/install/`, or the connected team name with a
  "Disconnect" POST button. Hidden entirely when the env var is empty.
- Two number inputs, "Reminder interval (days)" and "Maximum reminders",
  saved with the other organization fields and respecting
  `env_managed_fields()` like the rest.

### Files

```
slack/
  __init__.py
  apps.py
  models.py                 SlackWorkspace
  client.py                 api_call(token, method, **payload), verify_signature(request),
                            lookup_user(workspace, email), user_email(workspace, slack_user_id), deliver(...)
  blocks.py                 create_modal(questionnaires), dm_blocks(text, url, button), status_text(cycles)
  views.py                  install, oauth_callback, commands, interactions
  urls.py
  migrations/0001_initial.py
  management/commands/send_reviewer_reminders.py
  tests/
docs/slack-manifest.yaml    app manifest with placeholder domain
docs/ADMIN_GUIDE.md         new "Slack" section: hosted connect, self-hosted app creation, env vars
```

Touched: `blik/settings.py` (three env vars, `slack` in `INSTALLED_APPS`),
`blik/urls.py` (`path('slack/', include('slack.urls'))`), `blik/admin_views.py`
(settings view), `templates/admin_dashboard/settings.html`,
`reviews/services.py` (four `deliver` call sites, `reminder_count` bump),
`api/signals.py` (report-ready DM), `core/models.py`, `reviews/models.py`,
`docker-entrypoint.sh`.

### `api_call`

```python
def api_call(token, method, **payload):
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.load(resp)
    if not body.get("ok"):
        raise SlackError(body.get("error", "unknown"))
    return body
```

`oauth.v2.access` and `users.lookupByEmail` take form-encoded bodies, so
`api_call` sends `application/x-www-form-urlencoded` for those two methods
and JSON otherwise.

## Part 5: Error handling summary

| Situation | Behaviour |
|---|---|
| Bad or stale Slack signature | 401, body not parsed |
| Caller's Slack email not a Blik user in the org | Ephemeral message, nothing created |
| Caller lacks create permission | Ephemeral message, nothing created |
| No cycle credits | Modal field error on `reviewee`, transaction rolled back |
| Selected Slack user has no email | Modal field error on that block |
| Invalid external email | Modal field error on `external` |
| `lookupByEmail` miss or Slack API error while delivering | Email fallback, warning logged |
| Invitation thread raises | Logged, same as webhook thread today; cycle exists, admin can resend from the web UI |
| Tampered or expired OAuth `state` | 400, nothing stored |
| Workspace already connected to another org | Callback refuses with a settings-page error |

## Part 6: Testing

Unit tests per logical unit, no page smoke tests.

- `verify_signature`: valid signature passes; wrong secret fails; timestamp
  older than 300s fails.
- Due-token query: one test per condition in Part 3, each flipping exactly
  one condition from a due baseline and asserting exclusion; one asserting
  the baseline is included.
- Submission handler, given an already-resolved payload: creates reviewee
  when missing and reuses when present; creates one cycle and the expected
  tokens per category with lowercased deduplicated emails; the reviewee's
  own email is dropped from reviewer lists; `NoCycleCredits` yields a
  `reviewee` field error and no cycle row.
- `deliver` with `api_call` stubbed: Slack path when lookup hits; email path
  when lookup misses, when no workspace exists, and when `chat.postMessage`
  fails after a hit.
- OAuth callback: stores an encrypted token that round-trips through the
  property; refuses a tampered `state`; refuses a `team_id` already bound to
  another org.
- `send_reminder_emails` bumps `reminder_count` once per sent token.

Manual verification is the dogfood install on Blik's own workspace.

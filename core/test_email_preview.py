"""Unit test for the email preview frame used by capture_screenshots."""
from html import unescape

from django.test import SimpleTestCase

from core.management.commands.capture_screenshots import render_email_preview


class RenderEmailPreviewTests(SimpleTestCase):
    def test_embeds_rendered_email_and_escapes_headers(self):
        html = render_email_preview(
            'emails/reviewer_invitation',
            'Feedback for <Emma> & co',
            'peer@example.com',
            {'reviewee_name': 'Emma Davis', 'category': 'Peer',
             'feedback_url': 'https://example.com/feedback/abc/',
             'questionnaire_name': 'Software Engineering 360 Review'},
            'dark',
        )

        self.assertIn('Feedback for &lt;Emma&gt; &amp; co', html)
        srcdoc = unescape(html.split('srcdoc="', 1)[1].split('"></iframe>', 1)[0])
        self.assertIn('href="https://example.com/feedback/abc/"', srcdoc)
        self.assertIn('<strong>Emma Davis</strong>', srcdoc)

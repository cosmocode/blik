from django.test import SimpleTestCase, override_settings

from core.url import get_absolute_url


@override_settings(SITE_PROTOCOL='https', SITE_DOMAIN='blik.example')
class GetAbsoluteUrlTests(SimpleTestCase):
    def test_a_view_name_with_arguments(self):
        url = get_absolute_url('review_cycle_detail', cycle_uuid='0c4a9e1e-5d33-4c39-9f0c-1b2a3c4d5e6f')

        self.assertEqual(url, 'https://blik.example/dashboard/cycles/0c4a9e1e-5d33-4c39-9f0c-1b2a3c4d5e6f/')

    def test_a_path(self):
        self.assertEqual(get_absolute_url('/landing/dreyfus-model/'), 'https://blik.example/landing/dreyfus-model/')

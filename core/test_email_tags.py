from django.template import Context, Template, TemplateSyntaxError
from django.test import SimpleTestCase
from django.utils import translation


class HeadlineTagTests(SimpleTestCase):
    def render(self, source, **context):
        return Template('{% load i18n email_tags %}' + source).render(Context(context))

    def test_the_line_is_as_long_as_the_title(self):
        self.assertEqual(self.render("{% headline '=' %}Reset Your Password{% endheadline %}"),
                         'Reset Your Password\n===================')

    def test_the_line_follows_the_translated_title(self):
        with translation.override('de'):
            output = self.render("{% headline '─' %} {{ title }} {% endheadline %}", title='Erste Schritte')

        self.assertEqual(output, 'Erste Schritte\n──────────────')

    def test_the_character_is_required(self):
        with self.assertRaises(TemplateSyntaxError):
            self.render('{% headline %}Title{% endheadline %}')

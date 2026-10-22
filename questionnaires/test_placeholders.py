"""{name} in question texts stands for the reviewee's first name."""
from django.test import SimpleTestCase

from questionnaires.placeholders import personalize


class PersonalizeTest(SimpleTestCase):

    def test_the_placeholder_becomes_the_first_name(self):
        self.assertEqual(personalize('Teilt {name} Wissen?', 'Dana Doe'), 'Teilt Dana Wissen?')

    def test_questionnaires_from_before_the_placeholder_get_the_name_in_english(self):
        text = "This person shares this person's knowledge"

        self.assertEqual(personalize(text, 'Dana'), "Dana shares Dana's knowledge")

    def test_a_text_with_the_placeholder_keeps_this_person(self):
        text = 'Does {name} help this person?'

        self.assertEqual(personalize(text, 'Dana'), 'Does Dana help this person?')

    def test_without_a_name_the_text_stays(self):
        self.assertEqual(personalize('Teilt {name} Wissen?', ''), 'Teilt {name} Wissen?')
        self.assertEqual(personalize('Teilt {name} Wissen?', '  '), 'Teilt {name} Wissen?')
        self.assertEqual(personalize('Teilt {name} Wissen?', None), 'Teilt {name} Wissen?')

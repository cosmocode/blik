"""
The reviewee's name in question texts and action items.

{name} stands for the reviewee's first name in every language. Questionnaires from before the placeholder say "This
person" instead, which is replaced in texts without the placeholder; that only works in English.
"""

NAME_PLACEHOLDER = '{name}'

# Replaced in texts without the placeholder, so questionnaires written before it keep showing the name
LEGACY_NAME_PHRASES = ['This person', 'this person']


def personalize(text, name):
    """
    text with the reviewee's first name in place of the placeholder. A text without the placeholder gets it in place of
    the legacy phrases; one with the placeholder means them as they are.
    """

    names = (name or '').split()

    if not names:
        return text

    first_name = names[0]

    if NAME_PLACEHOLDER in text:
        return text.replace(NAME_PLACEHOLDER, first_name)

    for phrase in LEGACY_NAME_PHRASES:
        text = text.replace(phrase, first_name)

    return text

"""
Action items of a question.

Every action item carries a key, so a translation can refer to the item while its text, threshold or stages change.
"""

from django.utils.crypto import get_random_string

KEY_LENGTH = 8


def add_action_item_keys(action_items):
    """Give every action item without a key a new one."""

    for item in action_items:
        if isinstance(item, dict) and not item.get('key'):
            item['key'] = get_random_string(KEY_LENGTH)

    return action_items

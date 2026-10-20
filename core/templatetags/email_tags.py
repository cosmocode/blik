from django import template

register = template.Library()


@register.tag
def headline(parser, token):
    """
    {% headline '=' %}Title{% endheadline %}: the title with a line of '=' just as long below it,
    for headings in plain-text emails, whose length changes with the language.
    """
    bits = token.split_contents()

    if len(bits) != 2:
        raise template.TemplateSyntaxError("'headline' takes the character of the line, e.g. {% headline '=' %}")

    nodelist = parser.parse(('endheadline',))
    parser.delete_first_token()

    return HeadlineNode(nodelist, parser.compile_filter(bits[1]))


class HeadlineNode(template.Node):
    def __init__(self, nodelist, character):
        self.nodelist = nodelist
        self.character = character

    def render(self, context):
        title = self.nodelist.render(context).strip()

        return f'{title}\n{self.character.resolve(context) * len(title)}'

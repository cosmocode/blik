"""
Which language a request or an email gets.

A person's own language comes first, then the browser, then the organization's default. Browsers
only ask for base languages, so a browser language with the same base as the organization's
default (de for de-informal) takes the organization's variant.

A variant such as de-informal only holds the texts that differ from its base language de, and
falls back to it for the rest.
"""
from django.conf import settings
from django.utils.translation import get_supported_language_variant
from django.utils.translation.trans_real import parse_accept_lang_header


def is_language(code):
    return code in dict(settings.LANGUAGES)


def language_name(code):
    return dict(settings.LANGUAGES).get(code, code)


def translation_languages(language):
    """The languages whose texts count for language, the most specific first: de-informal, then de."""
    base, *variant = language.split('-', 1)

    return [language, base] if variant else [language]


def get_base_language(language):
    """The language that a variant such as de-informal belongs to, de; a language without variant is its own base."""
    return translation_languages(language)[-1]


def default_language(organization):
    return organization.default_language if organization else settings.LANGUAGE_CODE


def browser_language(request):
    """The first supported language in Accept-Language, or None."""
    for code, quality in parse_accept_lang_header(request.headers.get('Accept-Language', '')):
        if code == '*':
            break
        try:
            return get_supported_language_variant(code)
        except LookupError:
            continue
    return None


def request_language(request, *preferred, organization=None):
    """The first preferred language that is set, else the browser's, else the organization's."""
    for code in preferred:
        if code and is_language(code):
            return code

    default = default_language(organization)
    browser = browser_language(request)

    if browser is None or get_base_language(browser) == get_base_language(default):
        return default

    return browser


def user_language(user, organization=None):
    """The language of emails to a user: their profile's, else their organization's default."""
    profile = getattr(user, 'profile', None)
    return recipient_language(
        getattr(profile, 'language', ''),
        organization=organization or getattr(profile, 'organization', None),
    )


def recipient_language(*preferred, organization=None):
    """The language of an email: the recipient's own, else the organization's default."""
    for code in preferred:
        if code and is_language(code):
            return code

    return default_language(organization)

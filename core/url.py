from urllib.parse import urlunsplit

from django.conf import settings
from django.shortcuts import resolve_url


def get_absolute_url(to, *args, **kwargs):
    """The full URL of a view name, model or path on SITE_DOMAIN, for links that leave the site, such as in emails.

    Emails also go out from cron, and behind a proxy a request's host can be an internal one the recipient cannot
    reach.
    """

    scheme, netloc = settings.SITE_PROTOCOL, settings.SITE_DOMAIN
    url = resolve_url(to, *args, **kwargs)
    components = scheme, netloc, url, '', ''

    return urlunsplit(components)

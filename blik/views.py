"""
Core views for Blik application
"""
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import translation
from django.views import i18n

from core.languages import is_language


def health_check(request):
    """Health check endpoint for monitoring"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'blik',
        'version': '0.1.0'
    })


def set_language(request):
    """Django's set_language, which also stores the choice on the user's profile."""
    response = i18n.set_language(request)
    language = request.POST.get('language')
    profile = getattr(request.user, 'profile', None)

    if request.method == 'POST' and profile and is_language(language):
        profile.language = language
        profile.save(update_fields=['language'])

    return response


class JavaScriptCatalog(i18n.JavaScriptCatalog):
    """The catalogue in the language of the page that loads it, which passes it as ?language=."""

    def get(self, request, *args, **kwargs):
        language = request.GET.get('language')

        if is_language(language):
            translation.activate(language)

        return super().get(request, *args, **kwargs)


def home(request):
    """Home page - redirect authenticated users to dashboard, others to login"""
    if request.user.is_authenticated:
        return redirect('admin_dashboard')
    return redirect('login')


def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, 'landing/404.html', status=404)


def handler500(request):
    """Custom 500 error handler"""
    return render(request, 'landing/500.html', status=500)

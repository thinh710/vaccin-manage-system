from functools import wraps

from django.middleware.csrf import CsrfViewMiddleware


def csrf_protect_session_api(view_func):
    """Enforce Django CSRF for DRF views that use the custom session user id."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        middleware = CsrfViewMiddleware(lambda req: None)
        middleware.process_request(request)
        response = middleware.process_view(request, wrapped, args, kwargs)
        if response is not None:
            return response
        return view_func(request, *args, **kwargs)

    wrapped.csrf_exempt = False
    return wrapped

from functools import wraps

from django.views.decorators.csrf import csrf_exempt

from .models import ApiToken
from .utils import error_response


def token_required(view):
    

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        parts = request.META.get("HTTP_AUTHORIZATION", "").split()
        if len(parts) != 2 or parts[0].lower() != "token":
            return error_response("Authentication token missing or malformed.", 401)
        try:
            token = ApiToken.objects.select_related("user").get(key=parts[1])
        except ApiToken.DoesNotExist:
            return error_response("Invalid token.", 401)
        user = token.user
        if not (user.is_active and user.is_staff):
            return error_response("Administrator access required.", 403)
        request.api_user = user
        return view(request, *args, **kwargs)

    return csrf_exempt(wrapped)

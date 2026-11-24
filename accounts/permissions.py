from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_requis(*roles):
    """Refuse l'accès côté serveur si le rôle de l'utilisateur n'est pas autorisé."""

    def decorateur(vue):
        @wraps(vue)
        def enveloppe(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return vue(request, *args, **kwargs)

        return login_required(enveloppe)

    return decorateur
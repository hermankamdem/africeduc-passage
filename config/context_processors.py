from django.conf import settings


def marque(request):
    return {"APP_NAME": settings.APP_NAME}
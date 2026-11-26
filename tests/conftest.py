import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def vider_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def pas_d_appel_ia_reel(settings):
    settings.ANTHROPIC_API_KEY = ""
import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_password_is_hashed_with_argon2():
    user = get_user_model().objects.create_user(
        username="u1", password="motdepasse-solide-42", role="parent"
    )
    assert user.password.startswith("argon2$")
    assert "motdepasse" not in user.password
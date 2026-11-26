import json
import urllib.error
import urllib.request

from django.conf import settings


class ErreurIA(Exception):
    """Service indisponible ou réponse inexploitable. Ne contient jamais la clé."""


class ClientAnthropic:
    URL = "https://api.anthropic.com/v1/messages"

    def completer(self, systeme, utilisateur, max_tokens):
        """Retourne (texte, tokens_entree, tokens_sortie)."""
        corps = json.dumps(
            {
                "model": settings.AI_MODEL,
                "max_tokens": max_tokens,
                "system": systeme,
                "messages": [{"role": "user", "content": utilisateur}],
            }
        ).encode()
        requete = urllib.request.Request(
            self.URL,
            data=corps,
            method="POST",
            headers={
                "content-type": "application/json",
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(requete, timeout=settings.AI_TIMEOUT_S) as reponse:
                donnees = json.loads(reponse.read().decode())
            texte = "".join(
                bloc.get("text", "") for bloc in donnees["content"] if bloc.get("type") == "text"
            )
            usage = donnees.get("usage", {})
            return texte, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            raise ErreurIA(type(e).__name__) from e


def get_client():
    return ClientAnthropic()
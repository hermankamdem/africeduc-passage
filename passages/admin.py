
from django.contrib import admin

from .models import Anomalie, Badge, AppelIA, JournalAudit, MessageSortant, Passage, Synthese


@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = (
        "eleve", "point", "heure_locale", "heure_corrigee",
        "ecart_horloge_s", "appareil", "etat_sync", "motif_rejet",
    )
    list_filter = ("etat_sync", "appareil")


@admin.register(MessageSortant)
class MessageSortantAdmin(admin.ModelAdmin):
    list_display = ("parent", "anomalie", "etat", "motif_non_envoi", "cree_le")
    list_filter = ("etat", "motif_non_envoi")
admin.site.register([Anomalie, Badge, JournalAudit, Synthese, AppelIA])
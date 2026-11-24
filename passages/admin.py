from django.contrib import admin

from .models import Anomalie, Badge, JournalAudit, MessageSortant, Passage, Synthese


@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = (
        "eleve", "point", "heure_locale", "heure_corrigee",
        "ecart_horloge_s", "appareil", "etat_sync", "motif_rejet",
    )
    list_filter = ("etat_sync", "appareil")


admin.site.register([Anomalie, Badge, JournalAudit, MessageSortant, Synthese])
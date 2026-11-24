from django.contrib import admin

from .models import (
    Eleve, Etablissement, ExceptionJour, Fenetre, Itineraire, ParentEleve, PointControle,
)

admin.site.register(
    [Etablissement, Itineraire, Eleve, ParentEleve, PointControle, Fenetre, ExceptionJour]
)
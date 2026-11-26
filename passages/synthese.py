import hashlib
import json
import re
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone

from school.models import Eleve

from . import ia
from .models import Anomalie, AppelIA, Passage, Synthese

TYPES = ["absence_passage", "hors_fenetre", "point_hors_itineraire", "double_scan", "badge_inactif"]
LIBELLES = {
    "absence_passage": ("passage attendu manquant", "passages attendus manquants"),
    "hors_fenetre": ("passage hors fenêtre", "passages hors fenêtre"),
    "point_hors_itineraire": ("passage à un point hors itinéraire", "passages à un point hors itinéraire"),
    "double_scan": ("double scan", "doubles scans"),
    "badge_inactif": ("badge désactivé présenté", "badges désactivés présentés"),
}

SYSTEME = (
    "Tu rédiges un court résumé en français pour un responsable d'école. "
    "On te donne des chiffres déjà calculés. Utilise uniquement ces chiffres, écrits en chiffres, "
    "sans jamais en calculer, déduire ou ajouter un autre. "
    'Réponds uniquement par un objet JSON de la forme {"texte": "..."} et rien d\'autre.'
)


class SortieInvalide(Exception):
    pass


# ---------- 1. Les chiffres sont calculés par le code ----------

def calculer_chiffres(etablissement, classe, jour):
    eleves = Eleve.objects.filter(etablissement=etablissement, classe=classe, etat=Eleve.Etat.ACTIF)
    effectif = eleves.count()
    debut = timezone.make_aware(datetime.combine(jour, time.min))
    presents = (
        Passage.objects.filter(
            eleve__in=eleves,
            etat_sync=Passage.EtatSync.VALIDE,
            heure_corrigee__gte=debut,
            heure_corrigee__lt=debut + timedelta(days=1),
        )
        .values("eleve_id")
        .distinct()
        .count()
    )
    par_type = dict(
        Anomalie.objects.filter(eleve__in=eleves, date=jour)
        .values_list("type")
        .annotate(n=Count("id"))
    )
    chiffres = {"effectif": effectif, "presents": presents, "absents": effectif - presents}
    chiffres.update({t: par_type.get(t, 0) for t in TYPES})
    chiffres["anomalies_total"] = sum(chiffres[t] for t in TYPES)
    return chiffres


def _s(n):
    return "s" if n > 1 else ""


def texte_gabarit(classe, jour, c):
    """Mode dégradé : sec mais exact."""
    texte = (
        f"Classe {classe}, {jour:%d/%m/%Y} : {c['presents']} élève{_s(c['presents'])} "
        f"présent{_s(c['presents'])} sur {c['effectif']}, {c['absents']} sans passage enregistré."
    )
    details = [
        f"{c[t]} {LIBELLES[t][1 if c[t] > 1 else 0]}" for t in TYPES if c[t] > 0
    ]
    texte += (" Anomalies : " + ", ".join(details) + ".") if details else " Aucune anomalie."
    return texte


# ---------- 2. La sortie du modèle est validée ----------

def extraire_nombres(texte):
    return [int(n) for n in re.findall(r"\d+", texte)]


def nombres_autorises(classe, jour, c):
    return set(c.values()) | set(extraire_nombres(classe)) | {jour.day, jour.month, jour.year}


def _nettoyer(brut):
    brut = brut.strip()
    if brut.startswith("```"):
        brut = re.sub(r"^```[a-zA-Z]*\s*", "", brut)
        brut = re.sub(r"\s*```$", "", brut)
    return brut


def valider_sortie(brut, classe, jour, c):
    """Schéma strict : {"texte": str} et aucun nombre qui ne vienne pas des chiffres calculés."""
    try:
        donnees = json.loads(_nettoyer(brut))
    except ValueError:
        raise SortieInvalide("pas du JSON")
    if not isinstance(donnees, dict) or set(donnees) != {"texte"}:
        raise SortieInvalide("schéma non conforme")
    texte = donnees["texte"]
    if not isinstance(texte, str):
        raise SortieInvalide("texte attendu")
    texte = texte.strip()
    if not 20 <= len(texte) <= 500:
        raise SortieInvalide("longueur hors limites")
    nombres = extraire_nombres(texte)
    if not set(nombres) <= nombres_autorises(classe, jour, c):
        raise SortieInvalide("nombre inventé")
    if c["presents"] not in nombres or c["effectif"] not in nombres:
        raise SortieInvalide("chiffres essentiels absents")
    return texte


# ---------- 3. Coût tracé et plafonné ----------

def cout_fcfa(tokens_entree, tokens_sortie):
    entree = Decimal(str(settings.AI_PRIX_ENTREE_FCFA_MTOK))
    sortie = Decimal(str(settings.AI_PRIX_SORTIE_FCFA_MTOK))
    return (Decimal(tokens_entree) * entree + Decimal(tokens_sortie) * sortie) / Decimal(1_000_000)


def depense_du_jour():
    total = AppelIA.objects.filter(cree_le__date=timezone.localdate()).aggregate(
        t=Sum("cout_estime_fcfa")
    )["t"]
    return total or Decimal("0")


def plafond_atteint(message_utilisateur):
    """Vrai si l'appel prévu ferait dépasser le plafond quotidien (estimation prudente)."""
    estimation = cout_fcfa(len(message_utilisateur) // 3 + 150, settings.AI_MAX_TOKENS_SORTIE)
    return depense_du_jour() + estimation > Decimal(str(settings.AI_PLAFOND_JOUR_FCFA))


def _journaliser(tokens_entree, tokens_sortie, succes, motif=""):
    AppelIA.objects.create(
        modele=settings.AI_MODEL,
        tokens_entree=tokens_entree,
        tokens_sortie=tokens_sortie,
        cout_estime_fcfa=cout_fcfa(tokens_entree, tokens_sortie),
        succes=succes,
        motif=motif,
    )


# ---------- 4. Orchestration ----------

def _empreinte(etablissement, classe, jour, chiffres):
    brut = json.dumps(
        {"e": etablissement.pk, "c": classe, "d": jour.isoformat(), "n": chiffres}, sort_keys=True
    )
    return hashlib.sha256(brut.encode()).hexdigest()


def _produire(classe, jour, chiffres):
    """Retourne (texte, origine, chemin)."""
    gabarit = texte_gabarit(classe, jour, chiffres)
    G = Synthese.Origine.GABARIT
    if not settings.ANTHROPIC_API_KEY:
        return gabarit, G, "gabarit_sans_cle"

    message = json.dumps(
        {"classe": classe, "date": jour.isoformat(), "chiffres": chiffres}, ensure_ascii=False
    )
    client = ia.get_client()
    for tentative in (1, 2):  # une seule nouvelle tentative
        if plafond_atteint(message):
            return gabarit, G, "gabarit_plafond"
        try:
            brut, t_in, t_out = client.completer(SYSTEME, message, settings.AI_MAX_TOKENS_SORTIE)
        except ia.ErreurIA as e:
            _journaliser(0, 0, False, str(e)[:100])
            return gabarit, G, "gabarit_erreur_service"
        _journaliser(t_in, t_out, True)
        try:
            texte = valider_sortie(brut, classe, jour, chiffres)
        except SortieInvalide:
            continue
        chemin = "modele" if tentative == 1 else "modele_apres_nouvel_essai"
        return texte, Synthese.Origine.MODELE, chemin
    return gabarit, G, "gabarit_sortie_invalide"


def generer_synthese(etablissement, classe, jour):
    chiffres = calculer_chiffres(etablissement, classe, jour)
    empreinte = _empreinte(etablissement, classe, jour, chiffres)
    cle = dict(etablissement=etablissement, classe=classe, date=jour, empreinte=empreinte)

    existante = Synthese.objects.filter(**cle).first()
    # Deux demandes identiques ne sont pas facturées deux fois.
    if existante and (existante.origine == Synthese.Origine.MODELE or not settings.ANTHROPIC_API_KEY):
        return existante

    texte, origine, chemin = _produire(classe, jour, chiffres)
    synthese, _ = Synthese.objects.update_or_create(
        **cle,
        defaults={"chiffres": chiffres, "texte": texte, "origine": origine, "chemin": chemin},
    )
    return synthese
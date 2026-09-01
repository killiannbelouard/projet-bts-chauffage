import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from io import StringIO


# =====================================================
# CHEMIN DU FICHIER CSV
# =====================================================

def get_desktop_path() -> Path:
    """
    Trouve automatiquement le dossier Bureau ou Desktop.
    Sur Raspberry, le dossier peut s'appeler Desktop.
    Sur certains systèmes en français, il peut s'appeler Bureau.
    """
    home = Path.home()

    desktop_fr = home / "Bureau"
    desktop_en = home / "Desktop"

    if desktop_fr.exists():
        return desktop_fr

    if desktop_en.exists():
        return desktop_en

    raise FileNotFoundError("Impossible de trouver le dossier Bureau/Desktop.")


# Le CSV est dans le dossier Convertisseur
CSV_PATH = get_desktop_path() / "Convertisseur" / "emplois.csv"


# =====================================================
# FONCTIONS DE NETTOYAGE
# =====================================================

def clean_text(value: str) -> str:
    """
    Nettoie un texte :
    - évite les valeurs None
    - supprime les retours à la ligne
    - remplace les espaces multiples par un seul espace
    """
    value = str(value or "")
    value = value.replace("\n", " ").replace("\r", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_room_name(value: str) -> str:
    """
    Normalise le nom d'une salle pour comparer correctement.

    Exemple :
    'SUD 07' devient 'SUD07'
    ' sud 07 ' devient aussi 'SUD07'
    """
    return "".join(clean_text(value).upper().split())


def normalize_for_filter(value: str) -> str:
    """
    Normalise un texte pour détecter les mots importants.

    Exemple :
    'ANNULÉ' devient 'ANNULE'
    """
    value = clean_text(value).upper()
    value = unicodedata.normalize("NFD", value)
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    return value


def is_cancelled_course(row: dict) -> bool:
    """
    Vérifie si une ligne du CSV correspond à un cours annulé.
    Même si importcsv.py laisse passer un cours annulé, planning.py l'ignore.
    """
    cours = normalize_for_filter(row.get("Cours", ""))

    if "ANNULE" in cours:
        return True

    if "CANCELLED" in cours:
        return True

    if "CANCELED" in cours:
        return True

    return False


# =====================================================
# LECTURE DU CSV
# =====================================================

def parse_dt(date_str: str, time_str: str) -> datetime:
    """
    Transforme une date + une heure du CSV en objet datetime Python.

    Exemple :
    Date = 28/04/2026
    Début = 08:10
    Résultat = datetime(2026, 4, 28, 8, 10)
    """
    return datetime.strptime(
        f"{date_str.strip()} {time_str.strip()}",
        "%d/%m/%Y %H:%M"
    )


def load_rows() -> list[dict]:
    """
    Charge toutes les lignes du fichier emplois.csv.
    Les cours annulés sont ignorés.
    """
    if not CSV_PATH.exists():
        print(f"CSV introuvable : {CSV_PATH}")
        return []

    rows = []

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            clean_row = {
                "Salle": clean_text(row.get("Salle", "")),
                "Date": clean_text(row.get("Date", "")),
                "Début": clean_text(row.get("Début", "")),
                "Fin": clean_text(row.get("Fin", "")),
                "Cours": clean_text(row.get("Cours", "")),
            }

            # Sécurité : on ne garde pas les cours annulés
            if is_cancelled_course(clean_row):
                print(f"Cours annulé ignoré dans planning.py : {clean_row['Cours']}")
                continue

            rows.append(clean_row)

    return rows


def rows_for_room(salle: str) -> list[dict]:
    """
    Retourne uniquement les lignes correspondant à une salle.
    """
    salle_norm = normalize_room_name(salle)

    return [
        row for row in load_rows()
        if normalize_room_name(row["Salle"]) == salle_norm
    ]


# =====================================================
# CSV ENVOYÉ À L'ESP32
# =====================================================

def build_csv_for_room(salle: str) -> str:
    """
    Construit un CSV contenant seulement les cours de la salle demandée.
    Ce CSV peut être envoyé à l'ESP32.
    """
    rows = rows_for_room(salle)

    output = StringIO()

    writer = csv.DictWriter(
        output,
        fieldnames=["Salle", "Date", "Début", "Fin", "Cours"]
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(row)

    return output.getvalue()


# =====================================================
# COURS ACTUEL
# =====================================================

def prochain_cours(salle: str, now: datetime | None = None) -> str:
    """
    ATTENTION :
    La fonction garde le nom prochain_cours pour ne pas casser main.py.
    Mais maintenant elle retourne le COURS ACTUEL.

    Si un cours est en cours :
    → retourne par exemple : 08:10-12:35 (SC. TECHNIQUES IND.)

    Si aucun cours n'est en cours :
    → retourne : Aucun cours
    """
    salle_norm = normalize_room_name(salle)
    now = now or datetime.now()

    for row in load_rows():
        if normalize_room_name(row["Salle"]) != salle_norm:
            continue

        try:
            start = parse_dt(row["Date"], row["Début"])
            end = parse_dt(row["Date"], row["Fin"])
        except ValueError:
            continue

        cours = row["Cours"] or "COURS"

        # On vérifie si l'heure actuelle est entre le début et la fin du cours
        if start <= now < end:
            return f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} ({cours})"

    return "Aucun cours"

def cours_actuel(salle: str, now: datetime | None = None) -> str:
    """
    Retourne le cours actullement en cours.
                                        Cette fonction existe pour être utilisée par main.py
                                        """
    return prochain_cours(salle, now)


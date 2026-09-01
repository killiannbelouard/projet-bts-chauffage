import csv
import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Paris")


# =========================================================
# NETTOYAGE TEXTE
# =========================================================
def clean_text(value: str) -> str:
    """
    Nettoie un texte :
    - remplace les retours à la ligne
    - enlève les espaces multiples
    - enlève les espaces au début et à la fin
    """
    value = str(value or "")
    value = value.replace("\\n", " ")
    value = value.replace("\n", " ")
    value = value.replace("\r", " ")
    value = value.replace("\\,", ",")
    value = value.replace("\\;", ";")
    value = value.replace("\\:", ":")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_room(room: str) -> str:
    """
    Normalise le nom de salle.
    Exemple :
    Salle: SUD 07 -> SUD 07
    """
    room = clean_text(room)
    room = re.sub(r"^(salle\s*:\s*)", "", room, flags=re.IGNORECASE).strip()
    room = room.upper()

    if room:
        return room

    return "INCONNUE"


def normalize_for_filter(text: str) -> str:
    """
    Met en majuscules et enlève les accents.
    Exemple :
    ANNULÉ -> ANNULE
    """
    text = clean_text(text).upper()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def is_cancelled_event(summary: str, description: str, status: str) -> bool:
    """
    Vérifie si un cours est annulé.
    """
    full_text = (
        normalize_for_filter(summary)
        + " "
        + normalize_for_filter(description)
        + " "
        + normalize_for_filter(status)
    )

    if "ANNULE" in full_text:
        return True

    if "CANCELLED" in full_text:
        return True

    if "CANCELED" in full_text:
        return True

    return False


# =========================================================
# LECTURE ICS SANS BIBLIOTHEQUE ICALENDAR
# =========================================================
def unfold_ics_lines(text: str) -> list[str]:
    """
    Dans un fichier ICS, certaines lignes peuvent être coupées.
    Une ligne qui commence par un espace continue la ligne précédente.
    Cette fonction reconstitue les vraies lignes.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    raw_lines = text.split("\n")
    lines = []

    for line in raw_lines:
        if not line:
            continue

        # Ligne de continuation ICS
        if line.startswith(" ") or line.startswith("\t"):
            if lines:
                lines[-1] += line[1:]
        else:
            lines.append(line)

    return lines


def get_property_name(line: str) -> str:
    """
    Récupère le nom de propriété ICS.
    Exemple :
    DTSTART;TZID=Europe/Paris:20260602T080500
    -> DTSTART
    """
    before_colon = line.split(":", 1)[0]
    prop_name = before_colon.split(";", 1)[0]
    return prop_name.strip().upper()


def get_property_value(line: str) -> str:
    """
    Récupère la valeur après les deux-points.
    Nettoie aussi les apostrophes parasites.
    Exemple :
    DTSTART:'20260602T080500Z
    -> 20260602T080500Z
    """
    if ":" not in line:
        return ""

    value = line.split(":", 1)[1].strip()

    # Enlève les caractères parasites au début
    value = value.lstrip("'\"`’‘´ ")

    return clean_text(value)


def parse_ics_datetime(value: str):
    """
    Convertit une date ICS en datetime Europe/Paris.

    Formats acceptés :
    20260602T080500Z
    20260602T080500
    20260602
    """
    value = clean_text(value)
    value = value.lstrip("'\"`’‘´ ")

    # Cas avec UTC : 20260602T080500Z
    if re.match(r"^\d{8}T\d{6}Z$", value):
        dt_utc = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        return dt_utc.astimezone(LOCAL_TZ)

    # Cas sans fuseau : 20260602T080500
    if re.match(r"^\d{8}T\d{6}$", value):
        dt_local = datetime.strptime(value, "%Y%m%dT%H%M%S")
        return dt_local.replace(tzinfo=LOCAL_TZ)

    # Cas date seule : on ignore pour un emploi du temps
    if re.match(r"^\d{8}$", value):
        return None

    print(f"Date ignorée, format non reconnu : {value}")
    return None


def extract_events_from_ics(ics_path: str) -> list[dict]:
    """
    Lit le fichier ICS et extrait les événements VEVENT.
    """
    with open(ics_path, "rb") as f:
        raw = f.read()

    text = raw.decode("utf-8", errors="ignore")

    # Nettoyage global de sécurité
    text = text.replace("\x00", "")
    text = text.replace("\ufeff", "")

    lines = unfold_ics_lines(text)

    events = []
    current_event = None

    for line in lines:
        line = line.strip()

        if line == "BEGIN:VEVENT":
            current_event = {}
            continue

        if line == "END:VEVENT":
            if current_event is not None:
                events.append(current_event)
            current_event = None
            continue

        if current_event is None:
            continue

        if ":" not in line:
            continue

        prop_name = get_property_name(line)
        prop_value = get_property_value(line)

        current_event[prop_name] = prop_value

    return events


# =========================================================
# DEDUCTION DE LA SALLE
# =========================================================
def guess_room(summary: str, location: str) -> str:
    """
    Déduit la salle :
    1. LOCATION si présent
    2. Sinon dernière partie du SUMMARY s'il contient des tirets
    3. Sinon INCONNUE
    """
    location = normalize_room(location)

    if location != "INCONNUE":
        return location

    parts = [p.strip() for p in clean_text(summary).split("-")]

    if len(parts) >= 2:
        return normalize_room(parts[-1])

    return "INCONNUE"


# =========================================================
# CONVERSION ICS -> CSV
# =========================================================
def ics_to_csv(ics_path: str, csv_path: str):
    events = extract_events_from_ics(ics_path)

    rows = []

    for event in events:
        dtstart_value = event.get("DTSTART", "")
        dtend_value = event.get("DTEND", "")

        if not dtstart_value or not dtend_value:
            continue

        start = parse_ics_datetime(dtstart_value)
        end = parse_ics_datetime(dtend_value)

        if not start or not end:
            continue

        summary = clean_text(event.get("SUMMARY", ""))
        location = clean_text(event.get("LOCATION", ""))
        description = clean_text(event.get("DESCRIPTION", ""))
        status = clean_text(event.get("STATUS", ""))

        if is_cancelled_event(summary, description, status):
            print(f"Cours annulé ignoré : {summary}")
            continue

        salle = guess_room(summary, location)
        cours = summary.upper() if summary else "COURS"

        date_str = start.strftime("%d/%m/%Y")
        debut_str = start.strftime("%H:%M")
        fin_str = end.strftime("%H:%M")

        rows.append((start, [salle, date_str, debut_str, fin_str, cours]))

    # Tri par date et heure
    rows.sort(key=lambda x: x[0])

    # Suppression des doublons exacts
    cleaned_rows = []
    seen = set()

    for _, row in rows:
        key = tuple(row)

        if key in seen:
            continue

        seen.add(key)
        cleaned_rows.append(row)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Salle", "Date", "Début", "Fin", "Cours"])
        writer.writerows(cleaned_rows)

    print(f"OK: {len(cleaned_rows)} lignes exportées -> {csv_path}")


# =========================================================
# PROGRAMME PRINCIPAL
# =========================================================
if __name__ == "__main__":
    ics_to_csv("ept.ics", "emplois.csv")
import sys
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ED_LOGIN = "ED_LOGIN"
ED_PASSWORD = "ED_PASSWORD"

ROOM_NAME = "SUD 07"
BASE_URL = "https://www.ecoledirecte.com"


# =========================================================
# RECHERCHE DU DOSSIER BUREAU / DESKTOP
# =========================================================
def get_desktop_path():
    home = Path.home()

    desktop_fr = home / "Bureau"
    desktop_en = home / "Desktop"

    if desktop_fr.exists():
        return desktop_fr
    if desktop_en.exists():
        return desktop_en

    raise FileNotFoundError("Impossible de trouver le dossier Bureau/Desktop.")


# =========================================================
# DOSSIER CONVERTISSEUR SUR LE BUREAU
# =========================================================
DESKTOP_DIR = get_desktop_path()
CONVERTISSEUR_DIR = DESKTOP_DIR / "Convertisseur"
CONVERTISSEUR_DIR.mkdir(exist_ok=True)

IMPORT_SCRIPT = CONVERTISSEUR_DIR / "importcsv.py"
OUTPUT_FILE = CONVERTISSEUR_DIR / "ept.ics"


# =========================================================
# LECTURE DU PRESSE-PAPIERS
# =========================================================
def read_clipboard(page):
    return page.evaluate("() => navigator.clipboard.readText()")


# =========================================================
# TELECHARGEMENT DU FICHIER ICS AVEC PLAYWRIGHT REQUEST
# =========================================================
def download_ics_with_playwright(context, shared_url: str, output_path: Path):
    response = context.request.get(shared_url, timeout=60000)

    if not response.ok:
        raise RuntimeError(
            f"Erreur téléchargement ICS : HTTP {response.status} {response.status_text}"
        )

    content = response.text()

    if "BEGIN:VCALENDAR" not in content:
        print("Erreur : le fichier téléchargé n'est pas un vrai ICS.")
        print("URL utilisée :", shared_url)
        print("Aperçu du contenu :")
        print(content[:1000])
        raise ValueError("Le fichier téléchargé n'est pas un vrai fichier ICS.")

    output_path.write_text(content, encoding="utf-8")


# =========================================================
# LANCEMENT AUTOMATIQUE DE importcsv.py
# =========================================================
def run_importcsv():
    if not IMPORT_SCRIPT.exists():
        print(f"Le fichier importcsv.py est introuvable ici : {IMPORT_SCRIPT}")
        return

    print(f"Lancement de : {IMPORT_SCRIPT}")

    result = subprocess.run(
        [sys.executable, str(IMPORT_SCRIPT)],
        cwd=str(CONVERTISSEUR_DIR)
    )

    if result.returncode == 0:
        print("importcsv.py a été exécuté avec succès.")
    else:
        print(f"importcsv.py a retourné une erreur (code {result.returncode}).")


# =========================================================
# RECUPERATION DE LA VRAIE URL VIA BOUTON COPIER
# =========================================================
def get_share_url_via_browser(page):
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)

    # Connexion
    page.locator('input[type="text"]').first.fill(ED_LOGIN)
    page.locator('input[type="password"]').first.fill(ED_PASSWORD)
    page.locator("#connexion").click()
    page.wait_for_timeout(5000)

    # Navigation
    page.get_by_text("Consultation", exact=False).click()
    page.wait_for_timeout(3000)

    page.get_by_text("Salles", exact=False).click()
    page.wait_for_timeout(3000)

    page.get_by_text(ROOM_NAME, exact=False).click()
    page.wait_for_timeout(4000)

    page.get_by_text(
        f"EMPLOI DU TEMPS DE LA SALLE : {ROOM_NAME}",
        exact=False
    ).wait_for(timeout=10000)

    # Descendre jusqu'à la zone des agendas
    page.mouse.wheel(0, 1200)
    page.wait_for_timeout(1500)
    page.get_by_text("MES AGENDAS", exact=False).wait_for(timeout=10000)

    # Repérer la ligne du calendrier
    label = page.get_by_text(f"Emploi du temps Salle {ROOM_NAME}", exact=False)
    label.wait_for(timeout=10000)

    box = label.bounding_box()
    if not box:
        raise RuntimeError("Impossible de lire la position de la ligne.")

    # Clique à gauche de la ligne pour ouvrir le menu
    x = box["x"] - 40
    y = box["y"] + box["height"] / 2
    page.mouse.click(x, y)
    page.wait_for_timeout(2500)

    # Clique sur "Copier l'URL"
    copy_button = page.get_by_text("Copier l'URL", exact=False)
    copy_button.wait_for(timeout=10000)
    copy_button.click()
    page.wait_for_timeout(1500)

    shared_url = read_clipboard(page).strip()

    if not shared_url.startswith("http"):
        raise RuntimeError(f"URL copiée invalide : {shared_url}")

    return shared_url


# =========================================================
# PROGRAMME PRINCIPAL
# =========================================================
def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=400,
            args=["--start-maximized"]
        )

        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            permissions=["clipboard-read", "clipboard-write"]
        )

        page = context.new_page()

        try:
            shared_url = get_share_url_via_browser(page)
            print("URL récupérée :", shared_url)

            if OUTPUT_FILE.exists():
                OUTPUT_FILE.unlink()

            download_ics_with_playwright(context, shared_url, OUTPUT_FILE)
            print(f"Téléchargement terminé : {OUTPUT_FILE}")

            run_importcsv()

        finally:
            browser.close()


if __name__ == "__main__":
    main()

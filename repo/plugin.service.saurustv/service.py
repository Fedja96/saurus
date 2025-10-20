import time
import json
import urllib.request
import xbmc
import xbmcaddon
import xbmcgui
from datetime import datetime

ADDON = xbmcaddon.Addon()
DIALOG = xbmcgui.Dialog()
MONITOR = xbmc.Monitor()

def now_epoch():
    return int(time.time())

def read_json_https(url, timeout=6):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        raw = r.read()
        data = json.loads(raw)
        return data

def get_server_code_ttl_rotate():
    url = ADDON.getSetting("config_url")
    if not url:
        DIALOG.notification("SaurusTV", "Keine Config URL gesetzt", xbmcgui.NOTIFICATION_ERROR, 5000)
        return None, None, None
    try:
        data = read_json_https(url, 6)
        code = str(data.get("code", "")).strip()
        ttl = int(data.get("ttl", 0)) or 1209600
        rotates_at = data.get("rotates_at", "")
        DIALOG.notification("Debug Code aus JSON", code, xbmcgui.NOTIFICATION_INFO, 3000)
        DIALOG.notification("Debug TTL aus JSON", str(ttl), xbmcgui.NOTIFICATION_INFO, 3000)
        DIALOG.notification("Debug rotates_at aus JSON", rotates_at, xbmcgui.NOTIFICATION_INFO, 3000)
        return code, ttl, rotates_at
    except Exception as e:
        DIALOG.notification("SaurusTV", f"Konfig nicht erreichbar: {e}", xbmcgui.NOTIFICATION_ERROR, 4000)
        return None, None, None

def parse_utc_timestamp(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    except:
        return None

def cached_valid():
    try:
        verified_until = int(ADDON.getSetting("verified_until") or "0")
        valid = verified_until > now_epoch()
        DIALOG.notification("Debug Cached", f"verified_until={verified_until}, now={now_epoch()}, gültig={valid}", xbmcgui.NOTIFICATION_INFO, 3000)
        return valid
    except:
        return False

def remember_validity(ttl):
    until = now_epoch() + int(ttl)
    ADDON.setSetting("verified_until", str(until))
    DIALOG.notification("Debug Set Verified", f"verified_until gesetzt auf {until}", xbmcgui.NOTIFICATION_INFO, 3000)

def prompt_pin():
    try:
        pin = DIALOG.numeric(0, "PIN eingeben")
        return str(pin or "").strip()
    except:
        pin = DIALOG.input("PIN eingeben", type=xbmcgui.INPUT_PASSWORD)
        return str(pin or "").strip()

def main():
    delay = int(ADDON.getSetting("startup_delay") or 0)
    if delay > 0:
        for _ in range(delay):
            if MONITOR.abortRequested():
                return
            time.sleep(1)

    code, ttl, rotates_at = get_server_code_ttl_rotate()
    fallback_pin = ADDON.getSetting("fallback_pin").strip()
    last_rotate = ADDON.getSetting("last_rotate")

    # Prüfe ob Rotation vorliegt und Verifizierung zurücksetzen muss
    if rotates_at and last_rotate:
        server_rotate_dt = parse_utc_timestamp(rotates_at)
        last_rotate_dt = parse_utc_timestamp(last_rotate)
        if server_rotate_dt and last_rotate_dt and server_rotate_dt > last_rotate_dt:
            # Rotation erkannt, Verifizierung löschen
            ADDON.setSetting("verified_until", "0")
            DIALOG.notification("SaurusTV", "PIN Änderung erkannt, erneute Eingabe erforderlich", xbmcgui.NOTIFICATION_INFO, 4000)

    # Aktuelle Runtime Rotation speichern
    if rotates_at:
        ADDON.setSetting("last_rotate", rotates_at)

    # Prüfe ob Verifizierung noch gültig ist
    if cached_valid():
        return

    # Kein PIN konfiguriert?
    if not code and not fallback_pin:
        DIALOG.ok("SaurusTV", "Kein PIN verfügbar – Server prüfen oder Fallback PIN setzen.")
        return

    attempts = 3
    while attempts > 0 and not MONITOR.abortRequested():
        user_pin = prompt_pin()
        if user_pin == "":
            return

        if (code and user_pin == code) or (not code and fallback_pin and user_pin == fallback_pin):
            remember_validity(ttl)
            if ADDON.getSettingBool("show_success"):
                DIALOG.notification("SaurusTV", "PIN akzeptiert", xbmcgui.NOTIFICATION_INFO, 2500)
            return
        else:
            attempts -= 1
            if attempts > 0:
                DIALOG.ok("SaurusTV", f"Falscher PIN. Bleiben Versuche: {attempts}")
            else:
                DIALOG.ok("SaurusTV", "Zugriff verweigert. Kodi wird beendet.")
                time.sleep(1)
                xbmc.executebuiltin('Quit')
                return

if __name__ == "__main__":
    main()

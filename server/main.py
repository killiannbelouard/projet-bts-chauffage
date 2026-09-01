from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
from datetime import datetime

from planning import cours_actuel, build_csv_for_room
from db import init_db, insert_telemetry, get_last_telemetry

app = FastAPI()
clients: set[WebSocket] = set()


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "message": "Serveur radiateur connecté en ligne"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


async def broadcast(payload: dict):
    txt = json.dumps(payload, ensure_ascii=False)
    dead = []

    for c in clients:
        try:
            await c.send_text(txt)
        except Exception:
            dead.append(c)

    for c in dead:
        clients.discard(c)


def build_status_payload(
    room: str,
    temperature=None,
    heater=None,
    ts=None,
    current_override=None
) -> dict:
    """
    Construit les données à envoyer à l'affichage web.

    Fonctionnement normal :
    - le cours vient du CSV avec cours_actuel(room)

    Mode test :
    - si test_client.py envoie un champ "current",
      alors ce cours est affiché directement.
    """
    last = get_last_telemetry(room)

    if last:
        if temperature is None:
            temperature = last.get("temperature")

        if heater is None:
            heater = last.get("heater")

        if ts is None:
            ts = last.get("ts") or last.get("received_at")

    if heater is None:
        heater = "OFF"

    # Mode test : cours envoyé manuellement par test_client.py
    # Mode réel : cours lu dans le CSV
    if current_override:
        current_course = current_override
    else:
        current_course = cours_actuel(room)

    system = "OK"

    if current_course == "Aucun cours" and heater == "ON":
        system = "WARNING"

    return {
        "type": "telemetry",
        "data": {
            "room": room,
            "temperature": temperature,
            "heater": heater,
            "timestamp": ts,
            "current": current_course,
            "system": system
        },
        "server_time": now_iso()
    }


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    print("Client connecté")

    try:
        while True:
            msg_text = await ws.receive_text()
            print("Reçu :", msg_text)

            try:
                data = json.loads(msg_text)
            except json.JSONDecodeError:
                data = {"type": "unknown", "raw": msg_text}

            msg_type = data.get("type")

            if msg_type == "telemetry":
                room = str(data.get("room", "UNKNOWN")).strip()
                temperature = data.get("temperature")
                heater = data.get("heater")
                ts = data.get("timestamp")

                # Champ facultatif pour la démonstration
                # Si absent, le serveur utilise le CSV normalement
                current_override = data.get("current")

                insert_telemetry(
                    room=room,
                    temperature=temperature,
                    heater=heater,
                    ts=ts
                )

                await ws.send_text(json.dumps({
                    "type": "ack",
                    "room": room,
                    "server_time": now_iso()
                }, ensure_ascii=False))

                await broadcast(
                    build_status_payload(
                        room=room,
                        temperature=temperature,
                        heater=heater,
                        ts=ts,
                        current_override=current_override
                    )
                )
                continue

            if msg_type == "get_status":
                room = str(data.get("room", "SUD 07")).strip()

                await ws.send_text(json.dumps(
                    build_status_payload(room),
                    ensure_ascii=False
                ))
                continue

            if msg_type == "get_csv":
                room = str(data.get("room", "SUD 07")).strip()
                content = build_csv_for_room(room)

                await ws.send_text(json.dumps({
                    "type": "csv",
                    "room": room,
                    "content": content,
                    "server_time": now_iso()
                }, ensure_ascii=False))
                continue

            await ws.send_text(json.dumps({
                "type": "ack",
                "server_time": now_iso()
            }, ensure_ascii=False))

    except WebSocketDisconnect:
        print("Client déconnecté")
    finally:
        clients.discard(ws)
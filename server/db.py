import sqlite3 # Module standard pour utiliser SQLite
from pathlib import Path # Pour gérer proprement les chemins de fichiers
from datetime import datetime # Pour gérer les dates / heures
from typing import Optional, Dict, Any # Pour typer les fonctions (bonne pratique BTS)

# Chemin vers le fichier de base de données SQLite
# Le fichier sera créé automatiquement s’il n’existe pas
DB_PATH = Path(__file__).with_name("radiateur.db")

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with get_conn() as conn:
        conn.execute(""" create table if not exists telemetry (id integer primary key autoincrement,
                     room text not null, temperature real, heater text, ts text, received_at text not null)""")
        conn.execute("create index if not exists idx_telemetry_room on telemetry(room)")
        conn.execute("create index if not exists idx_telemetry_received_at on telemetry(received_at)")
        conn.commit()

def insert_telemetry(room: str, temperature: Optional[float], heater: Optional[str], ts: Optional[str]) -> None:
    received_at = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            "insert into telemetry (room, temperature, heater, ts, received_at) values (?, ?, ?, ?, ?)",
            (room, temperature, heater, ts, received_at),
        )
        conn.commit()

def get_last_telemetry(room: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "select room, temperature, heater, ts, received_at from telemetry where room = ? order by id desc limit 1",
            (room,),
        ).fetchone()
        return dict(row) if row else None

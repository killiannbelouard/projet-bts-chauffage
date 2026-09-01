// Salle affichée par défaut
const DEFAULT_ROOM = "SALLE";

// Connexion WebSocket vers le backend Raspberry
const WS_URL = `ws://${location.hostname}:9000/ws`;

const tbody = document.getElementById("tbody");
const wsState = document.getElementById("wsState");
const serverTime = document.getElementById("serverTime");

// On garde les salles en mémoire pour mettre à jour une ligne existante
const salles = new Map();


function setWsText(txt) {
  if (wsState) {
    wsState.textContent = txt;
  }
}


function setTimeText(txt) {
  if (serverTime) {
    serverTime.textContent = txt || "—";
  }
}


function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function fmtTemp(t) {
  if (t === null || t === undefined || t === "" || Number.isNaN(Number(t))) {
    return "—";
  }

  return `${Number(t).toFixed(1)} °C`;
}


function dotClass(heater) {
  return heater === "ON" ? "status-dot on" : "status-dot off";
}


function heaterLabel(heater) {
  if (heater === "ON") {
    return "Allumé";
  }

  if (heater === "OFF") {
    return "Éteint";
  }

  return heater || "Inconnu";
}


function systemClass(system) {
  if (system === "OK") {
    return "status-ok";
  }

  if (system === "ERROR") {
    return "status-error";
  }

  return "status-warning";
}


function renderTable() {
  if (!tbody) {
    return;
  }

  const rows = Array.from(salles.values()).sort((a, b) =>
    a.room.localeCompare(b.room)
  );

  tbody.innerHTML = rows
    .map((r) => {
      return `
        <tr>
          <td>${escapeHtml(r.room)}</td>
          <td>${fmtTemp(r.temperature)}</td>
          <td>
            <span class="${dotClass(r.heater)}"></span>
            ${escapeHtml(heaterLabel(r.heater))}
          </td>
          <td>${escapeHtml(r.current || r.next || "Aucun cours")}</td>
          <td class="${systemClass(r.system)}">${escapeHtml(r.system || "OK")}</td>
        </tr>
      `;
    })
    .join("");
}


function upsertTelemetry(message) {
  // Le serveur peut envoyer :
  // { type: "telemetry", data: {...}, server_time: "..." }
  // ou directement :
  // { type: "telemetry", room: "...", temperature: "...", etc. }
  const data = message.data ? message.data : message;

  const room = data.room || DEFAULT_ROOM;
  const heater = data.heater || "OFF";
  const system = data.system || "OK";

  // IMPORTANT :
  // current = nouveau nom pour "cours actuel"
  // next = ancien nom utilisé avant pour "prochain cours"
  // On accepte les deux pour éviter que l'affichage reste vide ou affiche "-"
  const current = data.current || data.next || "Aucun cours";

  salles.set(room, {
    room,
    temperature: data.temperature,
    heater,
    current,
    next: data.next,
    system,
  });

  renderTable();
}


function addDefaultRow() {
  salles.set(DEFAULT_ROOM, {
    room: DEFAULT_ROOM,
    temperature: null,
    heater: "OFF",
    current: "Aucun cours",
    next: null,
    system: "OK",
  });

  renderTable();
}


function connectWs() {
  setWsText("WS : connexion…");

  const ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setWsText("WS : connecté");

    // Demande l'état actuel de la salle au backend
    ws.send(JSON.stringify({
      type: "get_status",
      room: DEFAULT_ROOM,
    }));
  };

  ws.onclose = () => {
    setWsText("WS : déconnecté");
  };

  ws.onerror = () => {
    setWsText("WS : erreur");
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);

      if (msg.server_time) {
        setTimeText(msg.server_time);
      }

      if (msg.type === "ack") {
        return;
      }

      if (msg.type === "telemetry") {
        upsertTelemetry(msg);
        return;
      }

      if (msg.type === "csv") {
        console.log("CSV reçu :", msg.room, msg.content);
        return;
      }

    } catch (e) {
      console.log("Message non JSON :", event.data);
    }
  };
}


addDefaultRow();
connectWs();

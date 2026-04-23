const state = {
  connected: false,
  gameName: "Enigma del Einstein",
  gameObjective: "Encontrar al dueño del pez.",
  gameState: "Esperando conexión...",
  lastTag: {
    uid: "--",
    esp: "--",
    sensor: "--",
    attribute: "--",
    value: "--",
  },
  board: {},
  clues: [],
  backendLogs: [],
};

const connectionStatus = document.getElementById("connectionStatus");
const gameNameEl = document.getElementById("gameName");
const gameObjectiveEl = document.getElementById("gameObjective");
const gameStateEl = document.getElementById("gameState");
const lastUidEl = document.getElementById("lastUid");
const lastEspEl = document.getElementById("lastEsp");
const lastSensorEl = document.getElementById("lastSensor");
const lastAttributeEl = document.getElementById("lastAttribute");
const lastValueEl = document.getElementById("lastValue");
const cluesListEl = document.getElementById("cluesList");
const backendLogsEl = document.getElementById("backendLogs");
const boardCells = document.querySelectorAll("#gameBoard td[data-row][data-col]");
const introDismissButton = document.getElementById("introDismiss");
const showInfoButton = document.getElementById("showInfoButton");

// Elementos del panel de notificaciones
const notificationOverlay = document.getElementById("notificationOverlay");
const notificationPanel = document.getElementById("notificationPanel");
const notificationContent = document.getElementById("notificationContent");
const notificationClose = document.getElementById("notificationClose");

// Estado para rastrear si el pez fue detectado
let fishDetected = false;
let lastGameState = null;
let notificationTimeoutId = null;

const socket = io();

function updateConnectionStatus(connected) {
  state.connected = connected;
  connectionStatus.textContent = "";
  connectionStatus.setAttribute("aria-label", connected ? "Conectado" : "Desconectado");
  connectionStatus.classList.toggle("connected", connected);
  connectionStatus.classList.toggle("disconnected", !connected);
}

function updateGameInfo() {
  if (gameNameEl) {
    gameNameEl.textContent = state.gameName;
  }
  if (gameObjectiveEl) {
    gameObjectiveEl.textContent = state.gameObjective;
  }
  if (gameStateEl) {
    gameStateEl.textContent = state.gameState;
  }
}

function updateLastTag() {
  if (lastUidEl) lastUidEl.textContent = state.lastTag.uid;
  if (lastEspEl) lastEspEl.textContent = state.lastTag.esp;
  if (lastSensorEl) lastSensorEl.textContent = state.lastTag.sensor;
  if (lastAttributeEl) lastAttributeEl.textContent = state.lastTag.attribute;
  if (lastValueEl) lastValueEl.textContent = state.lastTag.value;
}

// Funciones para el panel de notificaciones
function showNotification(title, message, options = {}) {
  if (notificationTimeoutId) {
    clearTimeout(notificationTimeoutId);
  }

  const {
    imageUrl = null,
    isPersistent = false,
    autoHideDelay = 4000,
    statusType = null
  } = options;

  // Construir el contenido del panel
  notificationContent.innerHTML = "";

  if (imageUrl) {
    const image = document.createElement("img");
    image.src = imageUrl;
    image.alt = "Notificación";
    image.className = "notification-image";
    notificationContent.appendChild(image);
  }

  if (statusType) {
    const status = document.createElement("span");
    status.className = `notification-status ${statusType}`;
    status.textContent = statusType === "success" ? "¡VICTORIA!" : "JUEGO COMPLETADO";
    notificationContent.appendChild(status);
  }

  const titleEl = document.createElement("h2");
  titleEl.className = "notification-title";
  titleEl.textContent = title;
  notificationContent.appendChild(titleEl);

  if (message) {
    const messageEl = document.createElement("p");
    messageEl.className = "notification-message";
    messageEl.textContent = message;
    notificationContent.appendChild(messageEl);
  }

  // Mostrar el overlay
  notificationOverlay.classList.add("active");

  if (isPersistent) {
    // Notificación persistente (requiere cerrar manualmente)
    notificationOverlay.classList.add("persistent");
    notificationOverlay.classList.remove("auto-hide");
  } else {
    // Notificación temporal (auto-desaparece)
    notificationOverlay.classList.remove("persistent");
    notificationOverlay.classList.add("auto-hide");
    
    notificationTimeoutId = setTimeout(() => {
      hideNotification();
    }, autoHideDelay);
  }
}

function hideNotification() {
  if (notificationTimeoutId) {
    clearTimeout(notificationTimeoutId);
    notificationTimeoutId = null;
  }

  notificationOverlay.classList.remove("active", "persistent", "auto-hide");
  notificationContent.innerHTML = "";
}

function detectFishInBoard(boardData) {
  // Verificar si el pez fue colocado en la fila de mascotas (mascota: 3)
  const mascotaRow = boardData["mascota:3"] || boardData["mascota:4"] || 
                     boardData["mascota:1"] || boardData["mascota:2"] || 
                     boardData["mascota:5"];
  
  // En realidad, necesitamos verificar específicamente si "pez" está en alguna celda de mascota
  for (let col = 1; col <= 5; col++) {
    const cellKey = `mascota:${col}`;
    const cellValue = boardData[cellKey];
    if (cellValue && cellValue.toLowerCase().includes("pez")) {
      return true;
    }
  }
  return false;
}

const houseColorImageMap = {
  rojo: "red.jpg",
  azul: "blue.jpg",
  verde: "green.png",
  amarillo: "yellow.jpg",
  blanco: "white.png",
};

const nationalityImageMap = {
  denmark: "Denmark.png",
  england: "England.png",
  germany: "Germany.png",
  norway: "Norway.png",
  sweden: "Sweden.png",
  dinamarca: "Denmark.png",
  inglaterra: "England.png",
  alemania: "Germany.png",
  noruega: "Norway.png",
  suecia: "Sweden.png",
  ingles: "England.png",
  english: "England.png",
  englishman: "England.png",
  sueco: "Sweden.png",
  swedish: "Sweden.png",
  danes: "Denmark.png",
  danish: "Denmark.png",
  noruego: "Norway.png",
  norwegian: "Norway.png",
  aleman: "Germany.png",
  german: "Germany.png",
};

const petImageMap = {
  perro: "dog.png",
  dog: "dog.png",
  gato: "cat.png",
  cat: "cat.png",
  pajaro: "bird.png",
  bird: "bird.png",
  pez: "fish.png",
  fish: "fish.png",
  caballo: "horse.png",
  horse: "horse.png",
};

const drinkImageMap = {
  te: "tea.png",
  tea: "tea.png",
  cafe: "coffee.png",
  coffee: "coffee.png",
  leche: "milk.png",
  milk: "milk.png",
  cerveza: "beer.png",
  beer: "beer.png",
  agua: "water.png",
  water: "water.png",
};

const sweetsImageMap = {
  "chocolate": "chocolate.png",
  "galletas": "cookies.png",
  "paleta": "pallette.png",
  "pallette": "pallette.png",
  "caramelos": "candy.png",
  "malvaviscos": "marshmallows.png",
};

function normalizeText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[áàäâãå]/g, "a")
    .replace(/[éèëê]/g, "e")
    .replace(/[íìïî]/g, "i")
    .replace(/[óòöôõ]/g, "o")
    .replace(/[úùüû]/g, "u")
    .replace(/ñ/g, "n")
    .replace(/\s+/g, " ")
    .replace(/[_]+/g, " ");
}

function formatImageFilename(value) {
  if (!value) return "";
  return value[0].toUpperCase() + value.slice(1).toLowerCase() + ".png";
}

function renderBoardCell(cell, row, value) {
  const normalizedValue = normalizeText(value || "");

  if (row === "color") {
    const imageFile = houseColorImageMap[normalizedValue];
    if (imageFile) {
      cell.innerHTML = `<img src="images/chips/houses/${imageFile}" alt="${value}" />`;
      return;
    }
  }

  if (row === "nacionalidad") {
    const mappedFile = nationalityImageMap[normalizedValue];
    const imageFile = mappedFile || formatImageFilename(normalizedValue);
    if (imageFile) {
      cell.innerHTML = `<img src="images/chips/nationality/${imageFile}" alt="${value}" />`;
      return;
    }
  }

  if (row === "mascota") {
    const imageFile = petImageMap[normalizedValue];
    if (imageFile) {
      cell.innerHTML = `<img src="images/chips/pets/${imageFile}" alt="${value}" />`;
      return;
    }
  }

  if (row === "comida") {
    const imageFile = drinkImageMap[normalizedValue];
    if (imageFile) {
      cell.innerHTML = `<img src="images/chips/drinks/${imageFile}" alt="${value}" />`;
      return;
    }
  }

  if (row === "dulces") {
    const imageFile = sweetsImageMap[normalizedValue];
    if (imageFile) {
      cell.innerHTML = `<img src="images/chips/sweets/${imageFile}" alt="${value}" />`;
      return;
    }
  }

  cell.textContent = value || "-";
}

function renderBoard() {
  boardCells.forEach((cell) => {
    const row = cell.dataset.row;
    const col = cell.dataset.col;
    const key = `${row}:${col}`;
    const value = state.board[key] || "";
    renderBoardCell(cell, row, value);
  });
}

function renderClues() {
  cluesListEl.innerHTML = "";

  if (!state.clues.length) {
    cluesListEl.innerHTML = '<p class="empty-state">Las pistas se mostrarán aquí cuando el juego comience.</p>';
    return;
  }

  const boardHasPieces = Object.values(state.board).some((value) => value && value !== "");

  state.clues.forEach((clue) => {
    const clueItem = document.createElement("div");
    clueItem.className = "clue-item";

    const shouldShowFalse = boardHasPieces && clue.status === null;
    const visibleStatus = clue.status === true ? "✓" : clue.status === false ? "✗" : shouldShowFalse ? "✗" : "";
    const statusClass = shouldShowFalse ? "status-false" : getStatusClass(clue.status);

    const status = document.createElement("span");
    status.className = `clue-status ${statusClass}`;
    status.textContent = visibleStatus;

    const text = document.createElement("div");
    text.className = "clue-text";
    text.textContent = clue.description;

    clueItem.appendChild(status);
    clueItem.appendChild(text);
    cluesListEl.appendChild(clueItem);
  });
}

function renderBackendLogs() {
  if (!backendLogsEl) return;

  backendLogsEl.innerHTML = "";
  if (!state.backendLogs.length) {
    backendLogsEl.innerHTML = '<p class="empty-state">Esperando mensajes del backend...</p>';
    return;
  }

  state.backendLogs.slice(-10).reverse().forEach((log) => {
    const item = document.createElement("div");
    item.className = "backend-log-item";
    item.textContent = log.message;
    backendLogsEl.appendChild(item);
  });
}

function getStatusClass(status) {
  if (status === null) return "status-unknown";
  if (status === true) return "status-true";
  return "status-false";
}

function applyBoardData(boardData) {
  const newBoard = {};
  Object.entries(boardData).forEach(([row, cols]) => {
    Object.entries(cols).forEach(([col, value]) => {
      newBoard[`${row}:${col}`] = value || "";
    });
  });
  state.board = newBoard;
}

function applyCluesData(clues) {
  state.clues = Array.isArray(clues) ? clues : [];
}

function applyGameStatus(status) {
  if (!status) return;
  const previousGameState = state.gameState;
  state.gameState = status.game_state || state.gameState;
  applyBoardData(status.board || {});
  applyCluesData(status.clues || []);
  if (status.last_tag) {
    state.lastTag = {
      uid: status.last_tag.uid || "--",
      esp: status.last_tag.esp || "--",
      sensor: status.last_tag.sensor || "--",
      attribute: status.last_tag.attribute || "--",
      value: status.last_tag.value || "--",
    };
  }
  updateGameInfo();
  updateLastTag();
  renderBoard();
  renderClues();

  // Detectar si el pez fue colocado por primera vez
  const hasFishNow = detectFishInBoard(state.board);
  if (hasFishNow && !fishDetected) {
    fishDetected = true;
    showNotification(
      "El juego aún no ha acabado",
      "Completa todo el tablero para terminar",
      {
        autoHideDelay: 4000,
        statusType: "incomplete"
      }
    );
  }

  // Detectar cuando el juego se completa
  if (state.gameState === "completed" && previousGameState !== "completed") {
    // El juego se ha completado, mostrar mensaje de victoria/derrota
    const allCluesValid = status.clues && status.clues.every(clue => clue.status === true);
    
    if (allCluesValid) {
      // ¡Victoria!
      showNotification(
        "¡Felicidades ganaste el juego!",
        "Has resuelto correctamente el Enigma del Einstein",
        {
          imageUrl: "images/einstein_happy.png",
          isPersistent: true,
          statusType: "success"
        }
      );
    } else {
      // Derrota
      showNotification(
        "Juego Terminado",
        "Solución incorrecta. Intenta nuevamente.",
        {
          autoHideDelay: 5000,
          statusType: null
        }
      );
    }
  }
}

function addBackendLog(log) {
  if (!log || !log.message) return;
  state.backendLogs.push(log);
  if (state.backendLogs.length > 100) {
    state.backendLogs.shift();
  }
  renderBackendLogs();
}

async function fetchGameStatus() {
  try {
    const response = await fetch("/api/game/status");
    if (!response.ok) {
      throw new Error(`Error al cargar estado: ${response.status}`);
    }
    const status = await response.json();
    applyGameStatus(status);
  } catch (error) {
    console.error("No se puede obtener el estado del juego:", error);
  }
}

function updateState(newState) {
  Object.assign(state, newState);
  updateConnectionStatus(state.connected);
  updateGameInfo();
  updateLastTag();
  renderBoard();
  renderClues();
  renderBackendLogs();
}

socket.on("connect", () => {
  updateConnectionStatus(true);
  fetchGameStatus();
});

socket.on("disconnect", () => {
  updateConnectionStatus(false);
});

socket.on("game_state", (payload) => {
  applyGameStatus(payload);
});

socket.on("backend_log", (payload) => {
  addBackendLog(payload);
});

function hideIntroOverlay() {
  document.body.classList.remove("intro-active");
}

function showIntroOverlay() {
  document.body.classList.add("intro-active");
}

window.addEventListener("load", () => {
  document.body.classList.add("intro-active");
  if (introDismissButton) {
    introDismissButton.addEventListener("click", hideIntroOverlay);
  }
  if (showInfoButton) {
    showInfoButton.addEventListener("click", showIntroOverlay);
  }
  if (notificationClose) {
    notificationClose.addEventListener("click", hideNotification);
  }
  updateState(state);
  fetchGameStatus();
});

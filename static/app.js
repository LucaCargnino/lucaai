// STATE MANAGEMENT
let recordingActive = false;
let logEventSource = null;

// TABS SWITCHING
function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(`tab-${tabName}`).classList.add('active');
    document.getElementById(`tab-${tabName}-btn`).classList.add('active');
    
    if (tabName === 'settings') {
        loadSettings();
    }
}

// CONSOLE LOGGER
const consoleOutput = document.getElementById('console-output');

function writeToConsole(message, type = 'info') {
    if (!message || message.trim() === '') return;
    
    const span = document.createElement('span');
    span.textContent = message;
    
    // Assegna la classe CSS corretta basandosi sul tipo o contenuto del log
    if (type === 'thought' || message.includes('[Agent Thought]') || message.includes('Thinking Process:')) {
        span.className = 'agent-thought';
    } else if (message.includes('[-]')) {
        span.className = 'error-line';
    } else if (message.includes('[+]') || message.includes('=== RISULTATO')) {
        span.className = 'success-line';
    } else if (message.includes('[*]')) {
        span.className = 'info-line';
    } else if (message.includes('[SYSTEM]')) {
        span.className = 'system-line';
    } else {
        span.className = 'info-line';
    }
    
    consoleOutput.appendChild(span);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

function clearConsole() {
    consoleOutput.innerHTML = '';
    writeToConsole('[SYSTEM] Console ripulita.', 'system');
}

function copyConsole() {
    const text = consoleOutput.innerText;
    navigator.clipboard.writeText(text).then(() => {
        alert('Console copiata negli appunti!');
    }).catch(err => {
        console.error('Impossibile copiare il testo: ', err);
    });
}

// BACKEND API LOG STREAMING
function startLogStreaming() {
    if (logEventSource) {
        logEventSource.close();
    }
    
    logEventSource = new EventSource('/api/stream/logs');
    logEventSource.onmessage = function(event) {
        const data = event.data;
        writeToConsole(data);
    };
    
    logEventSource.onerror = function(err) {
        console.error("EventSource failed:", err);
        logEventSource.close();
    };
}

// DISABLE / ENABLE BUTTONS
function setButtonsState(disabled) {
    document.querySelectorAll('.action-btn').forEach(btn => {
        // Non disabilitare il pulsante di registrazione se è attivo
        if (btn.id === 'btn-record-meeting' && recordingActive) return;
        btn.disabled = disabled;
    });
}

// EXECUTE AGENTS
async function runEmailAgent() {
    clearConsole();
    writeToConsole("[*] Avvio dell'Agente Email & Report Word...", 'system');
    setButtonsState(true);
    
    try {
        const response = await fetch('/api/run/email', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'error') {
            writeToConsole(`[-] Errore: ${result.message}`, 'error');
        }
    } catch (err) {
        writeToConsole(`[-] Errore di rete: ${err.message}`, 'error');
    } finally {
        setButtonsState(false);
    }
}

async function runLeadAgent() {
    const query = document.getElementById('lead-query').value.trim();
    if (!query) {
        alert('Inserisci una query per cercare i lead!');
        return;
    }
    
    clearConsole();
    writeToConsole(`[*] Avvio dell'Agente Lead Finder per la query: "${query}"...`, 'system');
    setButtonsState(true);
    
    try {
        const response = await fetch('/api/run/lead', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        const result = await response.json();
        if (result.status === 'error') {
            writeToConsole(`[-] Errore: ${result.message}`, 'error');
        }
    } catch (err) {
        writeToConsole(`[-] Errore di rete: ${err.message}`, 'error');
    } finally {
        setButtonsState(false);
    }
}

async function runCalendarAgent() {
    clearConsole();
    writeToConsole("[*] Avvio dell'Agente Calendario & Promemoria...", 'system');
    setButtonsState(true);
    
    try {
        const response = await fetch('/api/run/calendar', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'error') {
            writeToConsole(`[-] Errore: ${result.message}`, 'error');
        }
    } catch (err) {
        writeToConsole(`[-] Errore di rete: ${err.message}`, 'error');
    } finally {
        setButtonsState(false);
    }
}

// RECORDING WORKFLOW
async function toggleMeetingRecording() {
    const btn = document.getElementById('btn-record-meeting');
    const text = document.getElementById('record-text');
    const visualizer = document.getElementById('audio-visualizer');
    
    if (!recordingActive) {
        // Avvia registrazione
        clearConsole();
        writeToConsole("[*] Connessione al microfono locale...", 'system');
        
        try {
            const response = await fetch('/api/run/meeting/start', { method: 'POST' });
            const result = await response.json();
            
            if (result.status === 'success') {
                recordingActive = true;
                btn.classList.add('recording');
                text.textContent = 'Ferma Registrazione';
                visualizer.style.display = 'flex';
                setButtonsState(true);
            } else {
                writeToConsole(`[-] Errore: ${result.message}`, 'error');
            }
        } catch (err) {
            writeToConsole(`[-] Errore di rete: ${err.message}`, 'error');
        }
    } else {
        // Ferma registrazione ed elabora verbale
        writeToConsole("[*] Arresto registrazione ed elaborazione del verbale in corso...", 'system');
        recordingActive = false;
        btn.classList.remove('recording');
        text.textContent = 'Avvia Registrazione';
        visualizer.style.display = 'none';
        
        try {
            const response = await fetch('/api/run/meeting/stop', { method: 'POST' });
            const result = await response.json();
            if (result.status === 'error') {
                writeToConsole(`[-] Errore: ${result.message}`, 'error');
            }
        } catch (err) {
            writeToConsole(`[-] Errore di rete: ${err.message}`, 'error');
        } finally {
            setButtonsState(false);
        }
    }
}

function showFallbackInput() {
    const container = document.getElementById('fallback-container');
    const btn = document.getElementById('btn-fallback-meeting');
    
    if (container.style.display === 'none') {
        container.style.display = 'block';
        btn.innerHTML = '<i class="fa-solid fa-square-xmark"></i> Nascondi Manuale';
    } else {
        container.style.display = 'none';
        btn.innerHTML = '<i class="fa-solid fa-keyboard"></i> Inserimento Manuale';
    }
}

async function runFallbackMeeting() {
    const text = document.getElementById('fallback-text').value.trim();
    if (!text) {
        alert('Inserisci del testo prima di inviare!');
        return;
    }
    
    clearConsole();
    writeToConsole("[*] Avvio elaborazione verbale da testo manuale...", 'system');
    setButtonsState(true);
    
    try {
        const response = await fetch('/api/run/meeting/fallback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript: text })
        });
        const result = await response.json();
        if (result.status === 'error') {
            writeToConsole(`[-] Errore: ${result.message}`, 'error');
        }
    } catch (err) {
        writeToConsole(`[-] Errore di rete: ${err.message}`, 'error');
    } finally {
        setButtonsState(false);
    }
}

// Modifica la textarea per inviare con il tasto invio modificato se desiderato, 
// o usiamo semplicemente un pulsante di invio all'interno del container fallback
document.getElementById('btn-fallback-meeting').insertAdjacentHTML('afterend', `
    <button class="action-btn secondary-btn" id="btn-submit-fallback" onclick="runFallbackMeeting()" style="margin-top: 5px; display: none;">
        <i class="fa-solid fa-paper-plane"></i> Elabora Testo
    </button>
`);

// Gestione visibilità pulsante invio manuale
const originalShowFallback = showFallbackInput;
showFallbackInput = function() {
    originalShowFallback();
    const container = document.getElementById('fallback-container');
    const submitBtn = document.getElementById('btn-submit-fallback');
    if (container.style.display === 'block') {
        submitBtn.style.display = 'flex';
    } else {
        submitBtn.style.display = 'none';
    }
};

// SETTINGS APIS
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        
        // Popola i campi del form
        for (const key in settings) {
            const input = document.getElementById(key);
            if (input) {
                input.value = settings[key] || '';
            }
        }
    } catch (err) {
        console.error('Impossibile caricare le impostazioni:', err);
    }
}

async function saveSettings(event) {
    event.preventDefault();
    const formData = new FormData(document.getElementById('settings-form'));
    const settings = {};
    
    formData.forEach((value, key) => {
        settings[key] = value.trim();
    });
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        const result = await response.json();
        if (result.status === 'success') {
            alert('Configurazione salvata con successo!');
            switchTab('dashboard');
            writeToConsole('[SYSTEM] File .env aggiornato.', 'system');
        } else {
            alert('Errore durante il salvataggio: ' + result.message);
        }
    } catch (err) {
        alert('Errore di rete: ' + err.message);
    }
}

// INIZIALIZZAZIONE ALL'AVVIO
window.addEventListener('DOMContentLoaded', () => {
    startLogStreaming();
});

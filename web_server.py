import os
import sys
import queue
import asyncio
import threading
import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Disabilita telemetria CrewAI per evitare blocchi firewall
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

def get_desktop_path():
    # Salva i report direttamente nella cartella lucaai
    return r"C:\od\OneDrive - NEXTERRA SRL\Desktop\lucaai"

class LogQueueStream:
    def __init__(self, original, q):
        self.original = original
        self.q = q
    def write(self, data):
        self.original.write(data)
        self.original.flush()
        # Non inviare righe vuote o codici di escape per pulire i log
        clean_data = data.strip()
        if clean_data and not clean_data.startswith("+------------------"):
            self.q.put(clean_data)
    def flush(self):
        self.original.flush()
    def isatty(self):
        return hasattr(self.original, 'isatty') and self.original.isatty()
    def __getattr__(self, name):
        return getattr(self.original, name)


log_queue = queue.Queue()
sys.stdout = LogQueueStream(sys.stdout, log_queue)
sys.stderr = LogQueueStream(sys.stderr, log_queue)

# Carica ambiente e helper locali
load_dotenv()
import email_helper
import docx_helper
import calendar_helper
import notifier_helper
import recorder_helper

# Importa agenti e librerie
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from duckduckgo_search import DDGS

app = FastAPI(title="Luca AI Control Center API")

@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.on_event("startup")
def startup_event():
    import whatsapp_bot
    # Avvia il polling del bot WhatsApp in background
    threading.Thread(target=whatsapp_bot.start_whatsapp_bot_polling, daemon=True).start()


# Stato globale per la registrazione audio
recording_stream = None
audio_blocks = []
SAMPLERATE = 44100

# -------------------------------------------------------------
# LLM OLLAMA CONFIGURATION
# -------------------------------------------------------------
def get_llms():
    OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return (
        LLM(model="ollama/llama3", base_url=OLLAMA_URL),
        LLM(model="ollama/llama3.2", base_url=OLLAMA_URL)
    )

# -------------------------------------------------------------
# DUCKDUCKGO SEARCH TOOL
# -------------------------------------------------------------
@tool("Ricerca Web DuckDuckGo")
def search_web_tool(query: str) -> str:
    """Cerca sul web informazioni, aziende, contatti o mercati usando DuckDuckGo."""
    try:
        print(f"\n[Strumento Ricerca] Ricerca web per: '{query}'...")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            if not results:
                return "Nessun risultato trovato per questa query."
            output_parts = []
            for idx, r in enumerate(results, 1):
                output_parts.append(
                    f"Risultato {idx}:\n"
                    f"Titolo: {r.get('title', 'N/A')}\n"
                    f"Link: {r.get('href', 'N/A')}\n"
                    f"Descrizione: {r.get('body', 'N/A')}\n"
                )
            return "\n---\n".join(output_parts)
    except Exception as e:
        return f"Errore durante la ricerca web: {e}"

# -------------------------------------------------------------
# PROMEMORIA TOOLS
# -------------------------------------------------------------
@tool("Invia Promemoria Email")
def send_email_tool(to_email: str, subject: str, message: str, from_email: str = None) -> str:
    """Invia un'email di promemoria a un destinatario. Puoi opzionalmente specificare 'from_email' per selezionare l'indirizzo mittente."""
    print(f"\n[Strumento Notifica] Invio e-mail a: {to_email} da {from_email or 'default'}...")
    success = notifier_helper.send_email_notification(to_email, subject, message, from_email=from_email)
    return "Email di promemoria inviata con successo!" if success else "Errore o credenziali mancanti per l'invio dell'email."

@tool("Prepara Messaggio WhatsApp")
def send_whatsapp_tool(phone_number: str, message: str) -> str:
    """Genera e apre nel browser un link per inviare un messaggio WhatsApp a un numero di telefono."""
    print(f"\n[Strumento Notifica] Apertura WhatsApp Web per: {phone_number}...")
    success = notifier_helper.send_whatsapp_message(phone_number, message)
    return "WhatsApp preparato ed aperto nel browser con successo!" if success else "Errore nella preparazione del messaggio WhatsApp."

# -------------------------------------------------------------
# WORKFLOW WRAPPERS FOR BACKGROUND TASKS
# -------------------------------------------------------------
def execute_email_workflow():
    try:
        llama3, _ = get_llms()
        print("\n[*] Avvio Flusso Email in background...")
        emails_data = email_helper.get_all_accounts_emails()
        
        emails_text = ""
        if not emails_data:
            emails_text = "Nessuna nuova e-mail non letta è stata trovata negli account configurati."
            print("[!] Nessuna nuova email trovata. Verrà generato un report vuoto.")
        else:
            for idx, em in enumerate(emails_data, 1):
                emails_text += f"--- EMAIL {idx} ---\n"
                emails_text += f"Account: {em['account']}\n"
                emails_text += f"Mittente: {em['sender']}\n"
                emails_text += f"Oggetto: {em['subject']}\n"
                emails_text += f"Data: {em['date']}\n"
                emails_text += f"Corpo:\n{em['body']}\n\n"
        
        email_analyst = Agent(
            role="Analista Senior di Posta Elettronica",
            goal="Identificare i messaggi importanti, distinguere le comunicazioni aziendali urgenti dallo spam e definire le azioni operative necessarie.",
            backstory="Sei un assistente esecutivo virtuale estremamente ordinato. Analizzi ogni email cercando scadenze, richieste di clienti, problemi da risolvere o appuntamenti da confermare. Traduci le richieste in azioni pratiche.",
            llm=llama3,
            verbose=True
        )
        
        report_writer = Agent(
            role="Redattore di Report Operativi",
            goal="Riorganizzare le informazioni estratte dall'analista in un report strutturato e professionale pronto per la consultazione aziendale.",
            backstory="Sei uno scrittore tecnico meticoloso. Ti assicuri che le tabelle siano complete, che le priorità siano evidenziate in grassetto e che il report contenga titoli ben organizzati in Markdown per consentire una facile conversione.",
            llm=llama3,
            verbose=True
        )
        
        analysis_task = Task(
            description=(
                "Analizza la seguente lista di email e individua per ciascuna se è importante o se richiede azioni operative:\n\n"
                f"{emails_text}\n\n"
                "Se non ci sono email, indica chiaramente che la giornata non presenta attività da e-mail."
            ),
            expected_output="Una sintesi dettagliata di ogni e-mail rilevante con l'azione operativa da compiere ed il livello di priorità associato.",
            agent=email_analyst
        )
        
        report_task = Task(
            description=(
                "Prendi l'analisi prodotta e scrivi il report finale. Il report deve seguire questa struttura:\n"
                "# Report Giornaliero Operazioni\n"
                "Data del report: [Inserisci Data di oggi]\n\n"
                "## Tabella Riassuntiva delle Attività\n"
                "Crea una tabella in formato Markdown con le colonne: | Priorità | Account | Mittente | Oggetto | Azione Richiesta |\n\n"
                "## Dettaglio Operazioni\n"
                "Aggiungi una sezione per ciascuna email che richiede azione, spiegando brevemente il contesto.\n"
                "Usa il grassetto per le parole chiave principali. Mantieni il formato in Markdown pulito."
            ),
            expected_output="Il testo del report finale formattato in formato Markdown.",
            agent=report_writer
        )
        
        crew = Crew(
            agents=[email_analyst, report_writer],
            tasks=[analysis_task, report_task],
            process=Process.sequential
        )
        
        result = crew.kickoff()
        
        today_str = datetime.date.today().strftime("%Y%m%d")
        desktop_path = get_desktop_path()
        output_filepath = os.path.join(desktop_path, f"Report_Operazioni_{today_str}.docx")
        
        docx_helper.create_report_from_markdown(str(result), output_filepath)
        print(f"[+] FLUSSO COMPLETATO: Il file Word è stato salvato sul tuo Desktop come: 'Report_Operazioni_{today_str}.docx'")
    except Exception as e:
        print(f"[-] Errore Flusso Email: {e}")

def execute_lead_workflow(query: str):
    try:
        _, llama3_2 = get_llms()
        print(f"\n[*] Avvio Flusso Lead per '{query}' in background...")
        
        lead_finder = Agent(
            role="Investigatore Commerciale e Ricercatore Lead",
            goal="Individuare aziende, startup, o attività commerciali sul web che corrispondono alla query del target, raccogliendo i loro siti web e descrizioni.",
            backstory="Sei un esperto di analisi di mercato digitale e Lead Generation. Usi gli strumenti di ricerca in modo medico per estrarre informazioni chiave sulle aziende target.",
            tools=[search_web_tool],
            llm=llama3_2,
            verbose=True
        )
        
        marketing_copywriter = Agent(
            role="Copywriter Persuasivo e Marketing Specialist",
            goal="Analizzare la lista di lead trovati e creare una proposta di marketing su misura, inclusa una bozza di email di contatto accattivante.",
            backstory="Sei un copywriter esperto in campagne B2B. Sai come attirare l'attenzione di un potenziale cliente scrivendo un'email corta, d'impatto, focalizzata sui suoi benefici e priva di frasi fatte.",
            llm=llama3_2,
            verbose=True
        )
        
        search_task = Task(
            description=f"Usa lo strumento di ricerca web per trovare aziende, contatti o lead pertinenti per la richiesta: '{query}'. Raccogli il nome dell'azienda, il link del loro sito web e una descrizione del loro business.",
            expected_output="Una lista formattata di potenziali lead commerciali con relativi link ed informazioni.",
            agent=lead_finder
        )
        
        marketing_task = Task(
            description=(
                "Prendi la lista di lead commerciali trovata dal ricercatore. Per ciascun lead (o per il gruppo di lead target):\n"
                "1. Scrivi una breve sintesi di cosa fanno e perché sono un buon target.\n"
                "2. Prepara una bozza di e-mail di vendita personalizzata e persuasiva per invogliare il lead a collaborare o fissare una call.\n"
                "Il documento finale deve essere formattato in Markdown."
            ),
            expected_output="Un documento completo in formato Markdown con l'analisi dei lead ed i testi delle e-mail di vendita pronte da inviare.",
            agent=marketing_copywriter
        )
        
        crew = Crew(
            agents=[lead_finder, marketing_copywriter],
            tasks=[search_task, marketing_task],
            process=Process.sequential
        )
        
        result = crew.kickoff()
        
        today_str = datetime.date.today().strftime("%Y%m%d")
        desktop_path = get_desktop_path()
        output_filepath = os.path.join(desktop_path, f"Bozza_Marketing_{today_str}.docx")
        
        docx_helper.create_report_from_markdown(str(result), output_filepath)
            
        print(f"[+] FLUSSO COMPLETATO: Il file di marketing è stato salvato come: 'Bozza_Marketing_{today_str}.docx'")
    except Exception as e:
        print(f"[-] Errore Flusso Lead: {e}")

def execute_calendar_workflow():
    try:
        _, llama3_2 = get_llms()
        print("\n[*] Avvio Flusso Calendario in background...")
        events_data = calendar_helper.get_all_upcoming_events(days=2)
        
        events_text = ""
        if not events_data:
            events_text = "Nessun evento o appuntamento trovato in agenda per i prossimi due giorni."
            print("[!] Nessun evento trovato in agenda. Verificare le credenziali se necessario.")
        else:
            for idx, ev in enumerate(events_data, 1):
                events_text += f"--- EVENTO {idx} ---\n"
                events_text += f"Calendario: {ev['source']}\n"
                events_text += f"Titolo: {ev['title']}\n"
                events_text += f"Inizio: {ev['start']}\n"
                events_text += f"Fine: {ev['end']}\n"
                events_text += f"Descrizione: {ev['description']}\n"
                events_text += f"Invitati: {', '.join(ev['attendees']) if ev['attendees'] else 'Nessuno'}\n\n"
                
        tomorrow_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        calendar_manager = Agent(
            role="Gestore dell'Agenda Personale",
            goal="Controllare gli eventi previsti per la giornata di domani e determinare quali richiedono l'invio di un promemoria preventivo al cliente/contatto.",
            backstory=(
                f"Sei un assistente esecutivo. Oggi è il {datetime.date.today().strftime('%Y-%m-%d')}. "
                f"Il tuo compito è scansionare gli appuntamenti per la data di domani ({tomorrow_date}). "
                "Se trovi un appuntamento di lavoro, un meeting o una call con dei clienti, devi estrarre i contatti."
            ),
            llm=llama3_2,
            verbose=True
        )
        
        notifier_agent = Agent(
            role="Agente Specialista in Notifiche",
            goal="Redigere un messaggio di promemoria e richiedere la conferma di presenza per gli appuntamenti di domani usando lo strumento appropriato.",
            backstory=(
                "Sei un addetto alle comunicazioni cordiale e professionale. "
                "Usa lo strumento 'Invia Promemoria Email' se trovi una mail del contatto. "
                "Usa lo strumento 'Prepara Messaggio WhatsApp' se trovi un numero di telefono."
            ),
            tools=[send_email_tool, send_whatsapp_tool],
            llm=llama3_2,
            verbose=True
        )
        
        calendar_task = Task(
            description=(
                f"Esamina i seguenti appuntamenti:\n\n{events_text}\n\n"
                f"Trova tutti gli appuntamenti previsti per domani ({tomorrow_date}). "
                "Se non trovi eventi per domani, segnalalo. Se trovi eventi, elenca per ciascuno: "
                "Titolo, Ora di inizio, e i dettagli del contatto (email e/o telefono)."
            ),
            expected_output="Un report dettagliato degli incontri previsti per domani e i recapiti dei contatti.",
            agent=calendar_manager
        )
        
        notify_task = Task(
            description=(
                "In base agli appuntamenti di domani identificati, invia i promemoria:\n"
                "- Se hai un'e-mail, chiama lo strumento 'Invia Promemoria Email'.\n"
                "- Se hai un numero di telefono, chiama lo strumento 'Prepara Messaggio WhatsApp'.\n"
                "Se non ci sono appuntamenti o se mancano i recapiti per tutti gli incontri, spiega cosa è stato riscontrato."
            ),
            expected_output="Un riassunto delle notifiche inviate o preparate.",
            agent=notifier_agent
        )
        
        crew = Crew(
            agents=[calendar_manager, notifier_agent],
            tasks=[calendar_task, notify_task],
            process=Process.sequential
        )
        
        result = crew.kickoff()
        print("\n=== RISULTATO ELABORAZIONE CALENDARIO ===")
        print(result)
        print("=========================================")
    except Exception as e:
        print(f"[-] Errore Flusso Calendario: {e}")

def execute_meeting_workflow(transcript: str):
    try:
        llama3, _ = get_llms()
        print("\n[*] Avvio Flusso Verbale Riunione in background...")
        
        meeting_analyst = Agent(
            role="Analista di Verbali e Trascrizioni",
            goal="Esaminare la trascrizione grezza di una riunione, evidenziando i punti chiave, le decisioni prese e le attività assegnate.",
            backstory="Sei un segretario di direzione esperto. Hai la capacità di leggere una trascrizione disordinata ed estrarre con estrema precisione l'essenza delle decisioni prese.",
            llm=llama3,
            verbose=True
        )
        
        minutes_writer = Agent(
            role="Redattore Professionista di Verbali di Riunione",
            goal="Prendere i punti chiave estratti e redigere un verbale formale ed elegante, con elenchi puntati e una tabella delle attività future.",
            backstory="Sei uno scrittore aziendale esperto. Organizzi i documenti con chiarezza, usando il grassetto per evidenziare i responsabili delle attività, e formattando il testo in Markdown affinché possa essere convertito in un report Word.",
            llm=llama3,
            verbose=True
        )
        
        analysis_task = Task(
            description=(
                "Analizza la seguente trascrizione di una riunione aziendale:\n\n"
                f"{transcript}\n\n"
                "Individua: i temi trattati, le decisioni più importanti prese e le attività/compiti assegnati a ciascuna persona."
            ),
            expected_output="Un report di analisi con i punti principali, le decisioni e i compiti emersi.",
            agent=meeting_analyst
        )
        
        minutes_task = Task(
            description=(
                "Prendi l'analisi e scrivi il verbale formale della riunione. Il verbale deve essere strutturato come segue:\n"
                "# Verbale di Riunione\n"
                "Data della riunione: [Data di oggi]\n\n"
                "## Sintesi Discussione\n"
                "[Un riassunto discorsivo di cosa si è discusso]\n\n"
                "## Decisioni Prese\n"
                "[Elenco ordinato delle decisioni prese]\n\n"
                "## Tabella Attività ed Azioni Future\n"
                "Crea una tabella in formato Markdown con le colonne: | Attività | Responsabile | Scadenza |\n"
                "Assegna scadenze ragionevoli se non esplicitate. Usa il formato grassetto per i nomi dei responsabili."
            ),
            expected_output="Il testo del verbale finale formattato in Markdown.",
            agent=minutes_writer
        )
        
        crew = Crew(
            agents=[meeting_analyst, minutes_writer],
            tasks=[analysis_task, minutes_task],
            process=Process.sequential
        )
        
        result = crew.kickoff()
        
        today_str = datetime.date.today().strftime("%Y%m%d")
        desktop_path = get_desktop_path()
        riunioni_folder = os.path.join(desktop_path, "Riunioni")
        os.makedirs(riunioni_folder, exist_ok=True)
        
        output_filepath = os.path.join(riunioni_folder, f"Verbale_Riunione_{today_str}.docx")
        
        docx_helper.create_report_from_markdown(str(result), output_filepath)
        print(f"[+] FLUSSO COMPLETATO: Il verbale di riunione è stato salvato sul tuo Desktop come: 'Riunioni/Verbale_Riunione_{today_str}.docx'")
    except Exception as e:
        print(f"[-] Errore Flusso Riunioni: {e}")

# -------------------------------------------------------------
# REST ENDPOINTS
# -------------------------------------------------------------
class LeadRequest(BaseModel):
    query: str

class MeetingRequest(BaseModel):
    transcript: str

@app.get("/api/settings")
def get_settings():
    load_dotenv()
    # Ritorna tutte le chiavi presenti nel .env
    keys = [
        "OLLAMA_BASE_URL",
        "EMAIL_1_IMAP_SERVER", "EMAIL_1_ADDRESS", "EMAIL_1_PASSWORD", "EMAIL_1_SMTP_SERVER", "EMAIL_1_SMTP_PORT",
        "EMAIL_2_IMAP_SERVER", "EMAIL_2_ADDRESS", "EMAIL_2_PASSWORD", "EMAIL_2_SMTP_SERVER", "EMAIL_2_SMTP_PORT",
        "EMAIL_3_IMAP_SERVER", "EMAIL_3_ADDRESS", "EMAIL_3_PASSWORD", "EMAIL_3_SMTP_SERVER", "EMAIL_3_SMTP_PORT",
        "EMAIL_4_IMAP_SERVER", "EMAIL_4_ADDRESS", "EMAIL_4_PASSWORD", "EMAIL_4_SMTP_SERVER", "EMAIL_4_SMTP_PORT",
        "SMTP_SERVER", "SMTP_PORT", "SMTP_SENDER_EMAIL", "SMTP_SENDER_PASSWORD",
        "GREEN_API_ID_INSTANCE", "GREEN_API_TOKEN_INSTANCE",
        "OPENAI_API_KEY",
        "OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET"
    ]
    return {k: os.getenv(k, "") for k in keys}

@app.post("/api/settings")
def save_settings(settings: dict):
    env_path = ".env"
    try:
        # Costruisci il testo del file .env
        lines = []
        for k, v in settings.items():
            lines.append(f"{k}={v}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        # Ricarica l'ambiente
        load_dotenv(override=True)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/run/email")
def run_email(background_tasks: BackgroundTasks):
    background_tasks.add_task(execute_email_workflow)
    return {"status": "success", "message": "Flusso Email avviato in background."}

@app.post("/api/run/lead")
def run_lead(req: LeadRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(execute_lead_workflow, req.query)
    return {"status": "success", "message": "Flusso Lead avviato in background."}

@app.post("/api/run/calendar")
def run_calendar(background_tasks: BackgroundTasks):
    background_tasks.add_task(execute_calendar_workflow)
    return {"status": "success", "message": "Flusso Calendario avviato."}

@app.post("/api/run/meeting/start")
def run_meeting_start():
    global recording_stream, audio_blocks
    if recording_stream:
        return {"status": "error", "message": "Registrazione già attiva."}
        
    try:
        import sounddevice as sd
        # Verifica se è presente un microfono
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        if not input_devices:
            return {"status": "error", "message": "Nessun microfono rilevato sul PC."}
            
        audio_blocks = []
        def callback(indata, frames, time, status):
            audio_blocks.append(indata.copy())
            
        recording_stream = sd.InputStream(samplerate=SAMPLERATE, channels=1, callback=callback, dtype='int16')
        recording_stream.start()
        print("\n[SYSTEM] Registrazione audio avviata dal microfono...")
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/run/meeting/stop")
def run_meeting_stop(background_tasks: BackgroundTasks):
    global recording_stream, audio_blocks
    if not recording_stream:
        return {"status": "error", "message": "Nessuna registrazione in corso."}
        
    try:
        recording_stream.stop()
        recording_stream.close()
        recording_stream = None
        
        import soundfile as sf
        import numpy as np
        
        filename = "temp_meeting.wav"
        if audio_blocks:
            recording = np.concatenate(audio_blocks, axis=0)
            sf.write(filename, recording, SAMPLERATE)
            audio_blocks = []
            
            # Avvia la trascrizione e l'agente in background
            def process_recording_background():
                print("[SYSTEM] Avvio trascrizione del file registrato...")
                transcript = recorder_helper.transcribe_audio_file(filename)
                
                # Rimuovi file temporaneo
                if os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except Exception:
                        pass
                        
                if transcript.strip():
                    print(f"[SYSTEM] Audio trascritto: {transcript[:150]}...")
                    execute_meeting_workflow(transcript)
                else:
                    print("[-] Impossibile completare il verbale: Trascrizione vuota.")
            
            background_tasks.add_task(process_recording_background)
            return {"status": "success", "message": "Registrazione fermata, elaborazione in corso."}
        else:
            return {"status": "error", "message": "Nessun dato audio catturato."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/run/meeting/fallback")
def run_meeting_fallback(req: MeetingRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(execute_meeting_workflow, req.transcript)
    return {"status": "success", "message": "Elaborazione verbale avviata."}

# -------------------------------------------------------------
# SSE STREAM LOGS ENDPOINT
# -------------------------------------------------------------
@app.get("/api/stream/logs")
async def get_log_stream():
    async def log_event_generator():
        # Prime event per agganciare la connessione
        yield "data: [SYSTEM] Connessione console stabilita.\n\n"
        while True:
            try:
                # Recupera e pulisci log dal stdout rediretto
                log_data = log_queue.get_nowait()
                # Rimuovi codici colore ANSI se presenti
                import re
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                clean_log = ansi_escape.sub('', log_data)
                
                # Invia log in formato SSE (data: messaggio \n\n)
                yield f"data: {clean_log}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.1)
                
    return StreamingResponse(log_event_generator(), media_type="text/event-stream")

# -------------------------------------------------------------
# STATIC FILES MOUNT (MOUNTED LAST!)
# -------------------------------------------------------------
from fastapi.responses import HTMLResponse

@app.get("/")
def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    response = HTMLResponse(content=html_content)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Avvia uvicorn locale su http://localhost:8000
    print("\n" + "="*50)
    print("  AVVIO LUCA AI CONTROL CENTER")
    print("  Apri il tuo browser su: http://localhost:8000")
    print("="*50 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

import os
import datetime
from dotenv import load_dotenv

# Disabilita telemetria CrewAI
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# Carica helper locali
import email_helper
import docx_helper
import calendar_helper
import notifier_helper

# Carica configurazioni dal file .env
load_dotenv()

# Inizializza i modelli Ollama locali
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Llama 3 per compiti testuali
llama3_llm = LLM(
    model="ollama/llama3",
    base_url=OLLAMA_URL
)

# Llama 3.2 per compiti che richiedono Tool/Function Calling
llama3_2_llm = LLM(
    model="ollama/llama3.2",
    base_url=OLLAMA_URL
)

def get_desktop_path():
    # Salva i report direttamente nella cartella lucaai
    return r"C:\od\OneDrive - NEXTERRA SRL\Desktop\lucaai"

# -------------------------------------------------------------
# NOTIFICATION TOOLS
# -------------------------------------------------------------
@tool("Invia Promemoria Email")
def send_email_tool(to_email: str, subject: str, message: str, from_email: str = None) -> str:
    """Invia un'email di promemoria a un destinatario. Puoi opzionalmente specificare 'from_email' per selezionare l'indirizzo mittente."""
    print(f"\n[Cron Notifica] Invio e-mail a: {to_email} da {from_email or 'default'}...")
    success = notifier_helper.send_email_notification(to_email, subject, message, from_email=from_email)
    return "Email di promemoria inviata con successo!" if success else "Errore o credenziali mancanti per l'invio dell'email."

@tool("Prepara Messaggio WhatsApp")
def send_whatsapp_tool(phone_number: str, message: str) -> str:
    """Genera e apre nel browser un link per inviare un messaggio WhatsApp a un numero di telefono."""
    print(f"\n[Cron Notifica] Apertura WhatsApp Web per il numero: {phone_number}...")
    success = notifier_helper.send_whatsapp_message(phone_number, message)
    return "WhatsApp preparato ed aperto nel browser con successo!" if success else "Errore nella preparazione del messaggio WhatsApp."

# -------------------------------------------------------------
# RUN EMAIL AGENT WORKFLOW
# -------------------------------------------------------------
def run_email_cron():
    print("\n" + "="*50)
    print(" [CRON] SCRITTURA REPORT EMAIL GIORNALIERO")
    print("="*50)
    
    emails_data = email_helper.get_all_accounts_emails()
    
    # Se non ci sono email non lette, non c'è bisogno di far girare gli agenti
    if not emails_data:
        print("[*] Nessuna nuova e-mail non letta trovata. Nessun report generato.")
        return
        
    print(f"[+] Trovate {len(emails_data)} e-mail non lette. Avvio agenti...")
    
    emails_text = ""
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
        llm=llama3_llm,
        verbose=True
    )
    
    report_writer = Agent(
        role="Redattore di Report Operativi",
        goal="Riorganizzare le informazioni estratte dall'analista in un report strutturato e professionale pronto per la consultazione aziendale.",
        backstory="Sei uno scrittore tecnico meticoloso. Ti assicuri che le tabelle siano complete, che le priorità siano evidenziate in grassetto e che il report contenga titoli ben organizzati in Markdown per consentire una facile conversione.",
        llm=llama3_llm,
        verbose=True
    )
    
    analysis_task = Task(
        description=(
            "Analizza la seguente lista di email e individua per ciascuna se è importante o se richiede azioni operative:\n\n"
            f"{emails_text}\n\n"
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
    print(f"[+] Report email generato e salvato in: {output_filepath}")

# -------------------------------------------------------------
# RUN CALENDAR AGENT WORKFLOW
# -------------------------------------------------------------
def run_calendar_cron():
    print("\n" + "="*50)
    print(" [CRON] SCANSIONE AGENDA E INVIO PROMEMORIA")
    print("="*50)
    
    events_data = calendar_helper.get_all_upcoming_events(days=2)
    
    # Filtra solo gli eventi previsti per domani
    tomorrow_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    tomorrow_events = []
    for ev in events_data:
        if tomorrow_date in ev['start']:
            tomorrow_events.append(ev)
            
    if not tomorrow_events:
        print("[*] Nessun appuntamento in agenda previsto per domani. Nessun promemoria da inviare.")
        return
        
    print(f"[+] Trovati {len(tomorrow_events)} appuntamenti per domani. Avvio agenti...")
    
    events_text = ""
    for idx, ev in enumerate(tomorrow_events, 1):
        events_text += f"--- EVENTO {idx} ---\n"
        events_text += f"Calendario: {ev['source']}\n"
        events_text += f"Titolo: {ev['title']}\n"
        events_text += f"Inizio: {ev['start']}\n"
        events_text += f"Fine: {ev['end']}\n"
        events_text += f"Descrizione: {ev['description']}\n"
        events_text += f"Invitati: {', '.join(ev['attendees']) if ev['attendees'] else 'Nessuno'}\n\n"

    calendar_manager = Agent(
        role="Gestore dell'Agenda Personale",
        goal="Controllare gli eventi previsti per la giornata di domani e determinare quali richiedono l'invio di un promemoria preventivo al cliente/contatto.",
        backstory=(
            f"Sei un assistente esecutivo. Oggi è il {datetime.date.today().strftime('%Y-%m-%d')}. "
            f"Il tuo compito è scansionare gli appuntamenti per la data di domani ({tomorrow_date}). "
            "Se trovi un appuntamento di lavoro, un meeting o una call con dei clienti, devi estrarre i contatti."
        ),
        llm=llama3_2_llm,
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
        llm=llama3_2_llm,
        verbose=True
    )
    
    calendar_task = Task(
        description=(
            f"Esamina i seguenti appuntamenti previsti per domani:\n\n{events_text}\n\n"
            "Elenca per ciascuno: Titolo, Ora di inizio, e i dettagli del contatto (email e/o telefono)."
        ),
        expected_output="Un report dettagliato degli incontri previsti per domani e i recapiti dei contatti.",
        agent=calendar_manager
    )
    
    notify_task = Task(
        description=(
            "In base agli appuntamenti di domani identificati, invia i promemoria:\n"
            "- Se hai un'e-mail, chiama lo strumento 'Invia Promemoria Email'.\n"
            "- Se hai un numero di telefono, chiama lo strumento 'Prepara Messaggio WhatsApp'.\n"
            "Se non trovi recapiti per gli incontri, spiega cosa è stato riscontrato."
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
    print("[+] Scansione e invio promemoria completati.")
    print(result)

def main():
    print(f"--- Esecuzione Silenziosa Agenti - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    run_email_cron()
    run_calendar_cron()
    print("--- Esecuzione completata ---")

if __name__ == "__main__":
    main()

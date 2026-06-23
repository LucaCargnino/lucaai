import os
import datetime
from dotenv import load_dotenv

# Disabilita telemetria CrewAI per evitare blocchi firewall aziendali
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from duckduckgo_search import DDGS

# Carica helper locali
import email_helper
import docx_helper
import calendar_helper
import notifier_helper
import recorder_helper

# Carica configurazioni dal file .env
load_dotenv()

def get_desktop_path():
    # Salva i report direttamente nella cartella lucaai
    return r"C:\od\OneDrive - NEXTERRA SRL\Desktop\lucaai"


# Inizializza i modelli Ollama locali
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Llama 3 per compiti puramente testuali (es. scrittura di report e verbali)
llama3_llm = LLM(
    model="ollama/llama3",
    base_url=OLLAMA_URL
)

# Llama 3.2 per compiti che richiedono Tool/Function Calling (più recente e compatibile con i Tool)
llama3_2_llm = LLM(
    model="ollama/llama3.2",
    base_url=OLLAMA_URL
)

# -------------------------------------------------------------
# STRUMENTI PER GLI AGENTI (TOOLS)
# -------------------------------------------------------------
@tool("Ricerca Web DuckDuckGo")
def search_web_tool(query: str) -> str:
    """Cerca sul web informazioni, aziende, contatti o mercati usando DuckDuckGo. Usalo per trovare informazioni su potenziali lead."""
    try:
        print(f"\n[Strumento Ricerca] Avvio ricerca per: '{query}'...")
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

@tool("Invia Promemoria Email")
def send_email_tool(to_email: str, subject: str, message: str, from_email: str = None) -> str:
    """Invia un'email di promemoria a un destinatario. Utile quando si dispone dell'indirizzo e-mail del contatto. Puoi opzionalmente specificare 'from_email' per selezionare l'indirizzo mittente (es. uno degli account configurati)."""
    print(f"\n[Strumento Notifica] Esecuzione invio e-mail a: {to_email} da {from_email or 'default'}...")
    success = notifier_helper.send_email_notification(to_email, subject, message, from_email=from_email)
    return "Email di promemoria inviata con successo!" if success else "Errore o credenziali mancanti per l'invio dell'email."

@tool("Prepara Messaggio WhatsApp")
def send_whatsapp_tool(phone_number: str, message: str) -> str:
    """Genera e apre nel browser un link per inviare un messaggio WhatsApp a un numero di telefono. Utile per contatti con numero di cellulare."""
    print(f"\n[Strumento Notifica] Apertura WhatsApp Web per il numero: {phone_number}...")
    success = notifier_helper.send_whatsapp_message(phone_number, message)
    return "WhatsApp preparato ed aperto nel browser con successo!" if success else "Errore nella preparazione del messaggio WhatsApp."

# -------------------------------------------------------------
# FLUSSO 1: LETTURA EMAIL E REPORT WORD
# -------------------------------------------------------------
def run_email_workflow():
    print("\n=============================================")
    print(" AVVIO FLUSSO: LETTURA EMAIL E REPORT WORD")
    print("=============================================\n")
    
    emails_data = email_helper.get_all_accounts_emails()
    
    emails_text = ""
    if not emails_data:
        emails_text = "Nessuna nuova e-mail non letta è stata trovata negli account configurati."
        print("[!] Nessuna nuova email trovata. Verrà generato un report di 'Nessuna Operazione'.")
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
    
    email_crew = Crew(
        agents=[email_analyst, report_writer],
        tasks=[analysis_task, report_task],
        process=Process.sequential
    )
    
    print("[*] Avvio elaborazione degli agenti...")
    result = email_crew.kickoff()
    
    today_str = datetime.date.today().strftime("%Y%m%d")
    desktop_path = get_desktop_path()
    output_filename = f"Report_Operazioni_{today_str}.docx"
    output_filepath = os.path.join(desktop_path, output_filename)
    
    print("\n[*] Generazione del file Word in corso...")
    docx_helper.create_report_from_markdown(str(result), output_filepath)
    
    print(f"\n[+] FLUSSO COMPLETATO: Il file Word è stato salvato sul tuo Desktop come: '{output_filename}'")

# -------------------------------------------------------------
# FLUSSO 2: RICERCA LEAD E MARKETING
# -------------------------------------------------------------
def run_lead_workflow():
    print("\n=============================================")
    print(" AVVIO FLUSSO: RICERCA LEAD E MARKETING")
    print("=============================================\n")
    
    lead_query = input("Inserisci il settore o la tipologia di lead da cercare (es. 'ristoranti biologici Milano'): ").strip()
    if not lead_query:
        lead_query = "software house Torino"
        print(f"Nessun input fornito. Verrà usata la query di default: '{lead_query}'")

    lead_finder = Agent(
        role="Investigatore Commerciale e Ricercatore Lead",
        goal="Individuare aziende, startup, o attività commerciali sul web che corrispondono alla query del target, raccogliendo i loro siti web e descrizioni.",
        backstory="Sei un esperto di analisi di mercato digitale e Lead Generation. Usi gli strumenti di ricerca in modo medico per estrarre informazioni chiave sulle aziende target.",
        tools=[search_web_tool],
        llm=llama3_2_llm,
        verbose=True
    )
    
    marketing_copywriter = Agent(
        role="Copywriter Persuasivo e Marketing Specialist",
        goal="Analizzare la lista di lead trovati e creare una proposta di marketing su misura, inclusa una bozza di email di contatto accattivante.",
        backstory="Sei un copywriter esperto in campagne B2B. Sai come attirare l'attenzione di un potenziale cliente scrivendo un'email corta, d'impatto, focalizzata sui suoi benefici e priva di frasi fatte.",
        llm=llama3_2_llm,
        verbose=True
    )
    
    search_task = Task(
        description=f"Usa lo strumento di ricerca web per trovare aziende, contatti o lead pertinenti per la richiesta: '{lead_query}'. Raccogli il nome dell'azienda, il link del loro sito web e una descrizione del loro business.",
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
    
    lead_crew = Crew(
        agents=[lead_finder, marketing_copywriter],
        tasks=[search_task, marketing_task],
        process=Process.sequential
    )
    
    print("[*] Avvio elaborazione degli agenti per i Lead...")
    result = lead_crew.kickoff()
    
    today_str = datetime.date.today().strftime("%Y%m%d")
    desktop_path = get_desktop_path()
    output_filename = f"Bozza_Marketing_{today_str}.docx"
    output_filepath = os.path.join(desktop_path, output_filename)
    
    print("\n[*] Generazione del file Word in corso...")
    docx_helper.create_report_from_markdown(str(result), output_filepath)
    
    print(f"\n[+] FLUSSO COMPLETATO: Il file di marketing è stato salvato come: '{output_filename}'")

# -------------------------------------------------------------
# FLUSSO 3: GESTIONE CALENDARI E PROMEMORIA
# -------------------------------------------------------------
def run_calendar_workflow():
    print("\n=============================================")
    print(" AVVIO FLUSSO: CALENDARIO E PROMEMORIA")
    print("=============================================\n")
    
    print("[*] Caricamento appuntamenti da Google ed Outlook per i prossimi 2 giorni...")
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
            "Se trovi un appuntamento di lavoro, un meeting o una call con dei clienti, devi estrarre i contatti "
            "(indirizzo email dagli invitati o numero di telefono dalla descrizione dell'evento)."
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
            "Usa lo strumento 'Prepara Messaggio WhatsApp' se trovi un numero di telefono (es. nella descrizione dell'evento). "
            "Il messaggio deve ricordare data, ora ed oggetto dell'incontro e richiedere gentilmente una conferma."
        ),
        tools=[send_email_tool, send_whatsapp_tool],
        llm=llama3_2_llm,
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
            "- Se hai un'e-mail, chiama lo strumento 'Invia Promemoria Email' scrivendo un oggetto chiaro e un corpo cordiale.\n"
            "- Se hai un numero di telefono, chiama lo strumento 'Prepara Messaggio WhatsApp' per aprire la chat precompilata.\n"
            "Se non ci sono appuntamenti o se mancano i recapiti per tutti gli incontri, spiega cosa è stato riscontrato."
        ),
        expected_output="Un riassunto delle notifiche inviate o preparate (email inviate con successo e link WhatsApp aperti).",
        agent=notifier_agent
    )
    
    calendar_crew = Crew(
        agents=[calendar_manager, notifier_agent],
        tasks=[calendar_task, notify_task],
        process=Process.sequential
    )
    
    print("[*] Avvio elaborazione degli agenti per il Calendario...")
    result = calendar_crew.kickoff()
    
    print("\n=== RISULTATO ELABORAZIONE CALENDARIO ===")
    print(result)
    print("=========================================")

# -------------------------------------------------------------
# FLUSSO 4: REGISTRAZIONE E VERBALE RIUNIONE
# -------------------------------------------------------------
def run_meeting_workflow():
    print("\n=============================================")
    print(" AVVIO FLUSSO: REGISTRAZIONE E VERBALE RIUNIONE")
    print("=============================================\n")
    
    # 1. Registra e trascrive l'audio
    transcript = recorder_helper.get_meeting_transcript()
    
    if not transcript.strip():
        print("[-] Trascrizione vuota. Impossibile generare un verbale di riunione.")
        return
        
    print(f"\n[+] Trascrizione ottenuta ({len(transcript)} caratteri).")
    print("--- Inizio Trascrizione ---")
    print(transcript[:300] + "..." if len(transcript) > 300 else transcript)
    print("---------------------------\n")
    
    # 2. Definisci gli agenti
    meeting_analyst = Agent(
        role="Analista di Verbali e Trascrizioni",
        goal="Esaminare la trascrizione grezza di una riunione, evidenziando i punti chiave, le decisioni prese e le attività assegnate.",
        backstory="Sei un segretario di direzione esperto. Hai la capacità di leggere una trascrizione disordinata (piena di ripetizioni, intercalari e frasi spezzate) ed estrarre con estrema precisione l'essenza delle decisioni prese.",
        llm=llama3_llm,
        verbose=True
    )
    
    minutes_writer = Agent(
        role="Redattore Professionista di Verbali di Riunione",
        goal="Prendere i punti chiave estratti e redigere un verbale formale ed elegante, con elenchi puntati e una tabella delle attività future.",
        backstory="Sei uno scrittore aziendale esperto. Organizzi i documenti con chiarezza, usando il grassetto per evidenziare i responsabili delle attività, e formattando il testo in Markdown affinché possa essere convertito in un report Word.",
        llm=llama3_llm,
        verbose=True
    )
    
    # 3. Definisci i task
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
            "[Un riassunto discorsivo ma sintetico di cosa si è discusso]\n\n"
            "## Decisioni Prese\n"
            "[Elenco ordinato delle decisioni prese durante l'incontro]\n\n"
            "## Tabella Attività ed Azioni Future\n"
            "Crea una tabella in formato Markdown con le colonne: | Attività | Responsabile | Scadenza |\n"
            "Assegna scadenze ragionevoli se non esplicitate. Usa il formato grassetto per i nomi dei responsabili."
        ),
        expected_output="Il testo del verbale formale formattato in Markdown.",
        agent=minutes_writer
    )
    
    # 4. Crea e avvia la Crew
    meeting_crew = Crew(
        agents=[meeting_analyst, minutes_writer],
        tasks=[analysis_task, minutes_task],
        process=Process.sequential
    )
    
    print("[*] Avvio elaborazione degli agenti per il verbale...")
    result = meeting_crew.kickoff()
    
    # 5. Salva il file Word nella cartella "Riunioni" sul Desktop
    today_str = datetime.date.today().strftime("%Y%m%d")
    desktop_path = get_desktop_path()
    # Crea la cartella "Riunioni" sul Desktop se non esiste
    riunioni_folder = os.path.join(desktop_path, "Riunioni")
    os.makedirs(riunioni_folder, exist_ok=True)
    
    output_filename = f"Verbale_Riunione_{today_str}.docx"
    output_filepath = os.path.join(riunioni_folder, output_filename)
    
    print("\n[*] Generazione del file Word in corso...")
    docx_helper.create_report_from_markdown(str(result), output_filepath)
    
    print(f"\n[+] FLUSSO COMPLETATO: Il verbale di riunione è stato salvato nella cartella sul Desktop: 'Riunioni/{output_filename}'")

# -------------------------------------------------------------
# MENU DI SELEZIONE PRINCIPALE
# -------------------------------------------------------------
def main():
    while True:
        print("\n=============================================")
        print("          BENVENUTO IN LUCA AI")
        print("=============================================")
        print("Scegli quale operazione avviare:")
        print("1. Analisi Email e Generazione Report Word (.docx)")
        print("2. Ricerca Lead e Bozza File Marketing (.md)")
        print("3. Gestione Calendari (Google/Outlook) e Promemoria")
        print("4. Registra Riunione e Genera Verbale (.docx)")
        print("5. Esegui Tutti i Flussi (1 + 2 + 3 + 4)")
        print("6. Esci")
        print("=============================================")
        
        scelta = input("Inserisci il numero corrispondente (1-6): ").strip()
        
        if scelta == "1":
            run_email_workflow()
        elif scelta == "2":
            run_lead_workflow()
        elif scelta == "3":
            run_calendar_workflow()
        elif scelta == "4":
            run_meeting_workflow()
        elif scelta == "5":
            run_email_workflow()
            run_lead_workflow()
            run_calendar_workflow()
            run_meeting_workflow()
        elif scelta == "6":
            print("\nGrazie per aver usato Luca AI! Arrivederci.\n")
            break
        else:
            print("\n[-] Scelta non valida. Riprova.")

if __name__ == "__main__":
    main()

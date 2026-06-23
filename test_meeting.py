import os
import datetime
from dotenv import load_dotenv

# Disabilita telemetria CrewAI per evitare blocchi firewall aziendali
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

from crewai import Agent, Task, Crew, Process, LLM
import docx_helper

# Carica configurazioni dal file .env
load_dotenv()

def get_desktop_path():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        path, _ = winreg.QueryValueEx(key, "Desktop")
        return os.path.expandvars(path)
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Desktop")


# Inizializza i modelli Ollama locali
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Llama 3 per compiti puramente testuali
llama3_llm = LLM(
    model="ollama/llama3",
    base_url=OLLAMA_URL
)

def run_test_meeting():
    print("--- Avvio Test non-interattivo Verbale Riunione ---")
    
    transcript = (
        "Riunione del team di marketing di Luca AI. "
        "Partecipanti: Luca, Marco, Anna. "
        "Luca dice: 'Dobbiamo lanciare la nuova campagna di marketing lunedì prossimo'. "
        "Marco risponde: 'Va bene, io mi occuperò di completare tutte le grafiche per i social entro questo venerdì'. "
        "Anna aggiunge: 'Ottimo, io preparerò la newsletter promozionale e la invierò mercoledì mattina così iniziamo a scaldare i contatti'."
    )
    
    print(f"[+] Trascrizione di prova: {transcript}")
    
    # 1. Definisci gli agenti
    meeting_analyst = Agent(
        role="Analista di Verbali e Trascrizioni",
        goal="Esaminare la trascrizione di una riunione per estrarre i punti chiave discussi, le decisioni e le azioni da intraprendere.",
        backstory="Sei un segretario di direzione esperto. Hai la capacità di leggere una trascrizione disordinata ed estrarre con estrema precisione l'essenza delle decisioni prese.",
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
    
    # 2. Definisci i task
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
    
    # 3. Crea e avvia la Crew
    meeting_crew = Crew(
        agents=[meeting_analyst, minutes_writer],
        tasks=[analysis_task, minutes_task],
        process=Process.sequential
    )
    
    print("[*] Esecuzione agenti...")
    result = meeting_crew.kickoff()
    
    # 4. Salva il file Word nella cartella "Riunioni" sul Desktop
    desktop_path = get_desktop_path()
    riunioni_folder = os.path.join(desktop_path, "Riunioni")
    os.makedirs(riunioni_folder, exist_ok=True)
    
    output_filepath = os.path.join(riunioni_folder, "Verbale_Test.docx")
    
    print("\n[*] Scrittura file Word...")
    docx_helper.create_report_from_markdown(str(result), output_filepath)
    print(f"[+] Test completato con successo! File salvato in: {output_filepath}")

if __name__ == "__main__":
    run_test_meeting()

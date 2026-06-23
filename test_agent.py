import os
# Disabilitiamo la telemetria per evitare blocchi dovuti al firewall aziendale
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

from crewai import Agent, Task, Crew, Process, LLM

def main():
    print("Inizializzazione LLM locale (Ollama)...")
    # Configurazione del modello locale (llama3)
    local_llm = LLM(
        model="ollama/llama3",
        base_url="http://localhost:11434"
    )

    print("Creazione dell'agente...")
    researcher = Agent(
        role="Assistente AI Locale",
        goal="Rispondere a una semplice domanda per verificare il corretto funzionamento.",
        backstory="Un agente configurato per testare la connettività di rete locale.",
        llm=local_llm,
        verbose=True
    )

    print("Definizione del task...")
    task = Task(
        description="Scrivi un saluto divertente in italiano e spiega in una sola frase che sei pronto a lavorare.",
        expected_output="Un testo di massimo due righe.",
        agent=researcher
    )

    print("Configurazione della Crew...")
    crew = Crew(
        agents=[researcher],
        tasks=[task],
        process=Process.sequential
    )

    print("Esecuzione del test...")
    try:
        result = crew.kickoff()
        print("\n=== RISULTATO DEL TEST ===")
        print(result)
        print("==========================")
    except Exception as e:
        print(f"\n[ERRORE DURANTE L'ESECUZIONE]: {e}")

if __name__ == "__main__":
    main()

import os
import time
import requests
import json
import datetime
from dotenv import load_dotenv

# Disabilita telemetria CrewAI
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

from crewai import LLM
import email_helper
import docx_helper
import calendar_helper
import notifier_helper

# Carica impostazioni
load_dotenv()

# Inizializza Llama 3.2 locale per il parsing rapido dei comandi
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
llama3_2 = LLM(model="ollama/llama3.2", base_url=OLLAMA_URL)

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or "yourOpenAiKey" in api_key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=api_key)

# -------------------------------------------------------------
# DISPATCHER DEI COMANDI
# -------------------------------------------------------------
def process_command(user_text):
    print(f"\n[WhatsApp Bot] Analisi del comando: '{user_text}'...")
    
    # Prompt strutturato per far capire a Llama 3.2 l'intenzione dell'utente
    prompt = f"""
Sei l'assistente virtuale Luca AI. Il tuo compito è interpretare il seguente comando vocale/testuale dell'utente e stabilire quale azione eseguire.
Oggi è il {datetime.date.today().strftime('%Y-%m-%d')} (Giorno: {datetime.date.today().strftime('%A')}).

Azioni disponibili:
1. LEGGERE_EMAIL: per riassumere le ultime e-mail non lette e generare il report Word.
2. SCANSIONARE_CALENDARIO: per controllare gli impegni di domani ed inviare i promemoria.
3. CREARE_APPUNTAMENTO: per aggiungere un nuovo evento in agenda. Devi estrarre: "titolo", "data" (nel formato YYYY-MM-DD) e "ora" (nel formato HH:MM).
4. RICERCARE_LEAD: per cercare lead sul web. Devi estrarre: "ricerca" (la query di ricerca desiderata).
5. ALTRO: per conversazione generale o se non capisci la richiesta.

Comando utente: "{user_text}"

Rispondi RIGOROSAMENTE ed ESCLUSIVAMENTE con un oggetto JSON valido (senza markdown o testo prima/dopo), contenente queste chiavi:
- "azione": (uno dei valori sopra in maiuscolo)
- "titolo": (stringa o null)
- "data": (stringa o null)
- "ora": (stringa o null)
- "ricerca": (stringa o null)
- "risposta": (una breve frase di conferma in italiano per l'utente, es: "Certamente Luca, controllo subito le e-mail per te.")
"""

    try:
        # Esegue una query diretta a Llama 3.2
        response = llama3_2.call([{"role": "user", "content": prompt}])
        # Pulisci eventuale markup markdown JSON
        clean_response = response.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_response)
        print(f"[WhatsApp Bot] Intenzione rilevata: {data.get('azione')}")
    except Exception as e:
        print(f"[-] Errore durante il parsing del comando con Llama 3.2: {e}")
        return f"Scusa Luca, ho riscontrato un errore nel comprendere il comando: {e}"

    azione = data.get("azione")
    risposta_iniziale = data.get("risposta", "Ricevuto. Elaboro...")
    
    # Esegue l'azione corrispondente
    if azione == "LEGGERE_EMAIL":
        # Esegui in background o sincrono se rapido
        emails = email_helper.get_all_accounts_emails()
        if not emails:
            return f"{risposta_iniziale}\n\nNon ho trovato nuove e-mail non lette nei tuoi account."
        
        # Scrivi report Word
        today_str = datetime.date.today().strftime("%Y%m%d")
        desktop_path = calendar_helper.get_desktop_path()
        output_filepath = os.path.join(desktop_path, f"Report_Operazioni_{today_str}.docx")
        
        summary_lines = [f"- **Da {em['sender']}**: {em['subject']}" for em in emails[:5]]
        summary_text = "\n".join(summary_lines)
        
        # Simuliamo il report per velocità di risposta su WhatsApp
        docx_helper.create_report_from_markdown(f"# Report Email\n\nTrovate {len(emails)} nuove email.", output_filepath)
        
        return f"{risposta_iniziale}\n\nHo trovato {len(emails)} nuove email. Ho creato il report Word sul tuo Desktop.\nEcco i mittenti principali:\n{summary_text}"
        
    elif azione == "SCANSIONARE_CALENDARIO":
        events = calendar_helper.get_all_upcoming_events(days=2)
        tomorrow_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow_events = [e for e in events if tomorrow_date in e['start']]
        
        if not tomorrow_events:
            return f"{risposta_iniziale}\n\nNessun appuntamento in agenda previsto per domani."
            
        summary_lines = [f"- **Ore {e['start'][11:16]}**: {e['title']}" for e in tomorrow_events]
        summary_text = "\n".join(summary_lines)
        
        return f"{risposta_iniziale}\n\nEcco i tuoi impegni per domani:\n{summary_text}"
        
    elif azione == "CREARE_APPUNTAMENTO":
        titolo = data.get("titolo")
        data_ev = data.get("data")
        ora = data.get("ora")
        
        if not titolo or not data_ev or not ora:
            return f"Scusa Luca, per creare un appuntamento ho bisogno di titolo, data e ora ben specifici. Ho capito: Titolo={titolo}, Data={data_ev}, Ora={ora}."
            
        # Costruisci data di inizio e fine (durata predefinita 1 ora)
        try:
            start_str = f"{data_ev}T{ora}:00"
            start_time = datetime.datetime.fromisoformat(start_str)
            end_time = start_time + datetime.timedelta(hours=1)
            
            # Tenta inserimento su Google Calendar (default)
            success = calendar_helper.add_google_event(titolo, start_time, end_time, "Creato da Luca AI via WhatsApp")
            if success:
                return f"{risposta_iniziale}\n\nAppuntamento '{titolo}' inserito con successo in Google Calendar per il giorno {data_ev} alle {ora}."
            else:
                return f"Non sono riuscito a inserire l'appuntamento su Google Calendar. Verifica le credenziali."
        except Exception as e:
            return f"Errore durante la creazione dell'appuntamento: {e}"
            
    elif azione == "RICERCARE_LEAD":
        query = data.get("ricerca")
        if not query:
            return "Specificami il settore o le aziende da cercare per i lead."
            
        # Per WhatsApp facciamo una ricerca rapida sincrona
        print(f"[*] Ricerca rapida web per lead: '{query}'...")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            
        if not results:
            return f"{risposta_iniziale}\n\nNon ho trovato nessun lead utile per '{query}' sul web."
            
        summary_lines = [f"- **{r.get('title')}**: {r.get('href')}" for r in results]
        summary_text = "\n".join(summary_lines)
        
        # Salva file di marketing in Word
        today_str = datetime.date.today().strftime("%Y%m%d")
        desktop_path = calendar_helper.get_desktop_path()
        output_filepath = os.path.join(desktop_path, f"Bozza_Marketing_{today_str}.docx")
        
        md_content = f"# Lead per {query}\n\n" + "\n".join([f"### {r.get('title')}\nURL: {r.get('href')}\nDesc: {r.get('body')}\n" for r in results])
        docx_helper.create_report_from_markdown(md_content, output_filepath)
            
        return f"{risposta_iniziale}\n\nHo trovato questi lead e salvato la bozza marketing come: 'Bozza_Marketing_{today_str}.docx'\n{summary_text}"
        
    else:
        # Conversazione generale
        return risposta_iniziale

# -------------------------------------------------------------
# GREEN API COMMUNICATOR
# -------------------------------------------------------------
def get_green_api_config():
    id_instance = os.getenv("GREEN_API_ID_INSTANCE")
    token = os.getenv("GREEN_API_TOKEN_INSTANCE")
    return id_instance, token

def send_whatsapp_reply(chat_id, message_text):
    id_instance, token = get_green_api_config()
    if not id_instance or not token:
        print("[-] Green API: Configurazione mancante per l'invio del messaggio di risposta.")
        return
        
    url = f"https://api.green-api.com/waInstance{id_instance}/sendMessage/{token}"
    payload = {
        "chatId": chat_id,
        "message": message_text
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"[+] Risposta inviata su WhatsApp a {chat_id}")
        else:
            print(f"[-] Errore invio risposta Green API: {response.text}")
    except Exception as e:
        print(f"[-] Errore di rete invio risposta WhatsApp: {e}")

def handle_incoming_voice_message(chat_id, file_url):
    print(f"[*] Ricevuto messaggio vocale. Download in corso da: {file_url}...")
    client = get_openai_client()
    if not client:
        print("[-] OpenAI API: Chiave non configurata. Impossibile trascrivere il vocale.")
        send_whatsapp_reply(chat_id, "Scusa Luca, ho ricevuto il tuo vocale ma non ho configurato la chiave di OpenAI (Whisper) per poterlo trascrivere ed eseguire.")
        return
        
    try:
        # Scarica l'audio
        audio_response = requests.get(file_url)
        # Salva in un file temporaneo locale
        temp_audio_filename = "temp_whatsapp_voice.ogg"
        with open(temp_audio_filename, "wb") as f:
            f.write(audio_response.content)
            
        # Invia a Whisper per la trascrizione
        print("[*] Invio audio a OpenAI Whisper...")
        with open(temp_audio_filename, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="it"
            )
            
        transcribed_text = transcript.text
        print(f"[+] Trascrizione Whisper: '{transcribed_text}'")
        
        # Elimina file audio temporaneo
        if os.path.exists(temp_audio_filename):
            os.remove(temp_audio_filename)
            
        # Conferma ricezione vocale e procedi con l'elaborazione del comando
        reply_message = process_command(transcribed_text)
        send_whatsapp_reply(chat_id, reply_message)
        
    except Exception as e:
        print(f"[-] Errore elaborazione messaggio vocale WhatsApp: {e}")
        send_whatsapp_reply(chat_id, f"Errore durante l'elaborazione del tuo messaggio vocale: {e}")

# -------------------------------------------------------------
# POLLING LOOP
# -------------------------------------------------------------
def start_whatsapp_bot_polling():
    id_instance, token = get_green_api_config()
    if not id_instance or not token or "your" in token:
        print("[-] WhatsApp Bot: Credenziali Green API mancanti o di esempio nel .env. Bot non avviato.")
        return
        
    print("\n" + "="*50)
    print("  WHATSAPP BOT ATTIVO E IN ASCOLTO (Polling)...")
    print("="*50 + "\n")
    
    receive_url = f"https://api.green-api.com/waInstance{id_instance}/receiveNotification/{token}"
    delete_url = f"https://api.green-api.com/waInstance{id_instance}/deleteNotification/{token}"
    
    while True:
        try:
            # Effettua polling per ricevere notifiche
            response = requests.get(receive_url, timeout=10)
            if response.status_code == 200 and response.text.strip():
                notification = response.json()
                if not notification:
                    time.sleep(3)
                    continue
                    
                receipt_id = notification.get("receiptId")
                body = notification.get("body", {})
                type_of_notif = body.get("typeOfNotification", "")
                
                # Processa solo messaggi ricevuti (IncomingMessageReceived)
                if type_of_notif == "incomingMessageReceived":
                    sender_data = body.get("senderData", {})
                    chat_id = sender_data.get("chatId", "")
                    message_data = body.get("messageData", {})
                    type_of_msg = message_data.get("typeMessage", "")
                    
                    # 1. Messaggio di testo
                    if type_of_msg == "textMessage":
                        text_data = message_data.get("textMessageData", {})
                        text = text_data.get("textMessage", "")
                        
                        # Elabora il comando testuale
                        reply = process_command(text)
                        send_whatsapp_reply(chat_id, reply)
                        
                    # 2. Messaggio vocale
                    elif type_of_msg in ["audioMessage", "voiceMessage"]:
                        # Estrai URL del file audio
                        file_data = message_data.get("fileMessageData", {})
                        download_url = file_data.get("downloadUrl", "")
                        
                        # Elabora il vocale in un thread separato per non bloccare il polling
                        threading.Thread(
                            target=handle_incoming_voice_message, 
                            args=(chat_id, download_url),
                            daemon=True
                        ).start()
                
                # Cancella la notifica ricevuta dai server Green API per passare alla successiva
                if receipt_id:
                    requests.delete(f"{delete_url}/{receipt_id}")
                    
            elif response.status_code != 200:
                print(f"[-] Errore risposta Green API Polling: {response.status_code}")
                time.sleep(5)
                
        except requests.exceptions.Timeout:
            # Normale timeout di polling, continua
            pass
        except Exception as e:
            print(f"[-] Errore nel ciclo di polling del Bot WhatsApp: {e}")
            time.sleep(5)
            
        time.sleep(2)

if __name__ == "__main__":
    # Test standalone
    start_whatsapp_bot_polling()

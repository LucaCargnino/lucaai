import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from O365 import Account

# Scopes per Google Calendar (Lettura e Scrittura)
GOOGLE_SCOPES = ['https://www.googleapis.com/auth/calendar']

# -------------------------------------------------------------
# GOOGLE CALENDAR HELPER
# -------------------------------------------------------------
def get_google_calendar_service():
    creds = None
    # Il file token.json memorizza i token di accesso dell'utente
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', GOOGLE_SCOPES)
        
    # Se non ci sono credenziali valide, fai il login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        
        if not creds:
            if not os.path.exists('credentials.json'):
                print("[-] Google Calendar: File 'credentials.json' non trovato.")
                print("    Scaricalo dalla Google Cloud Console (OAuth Client ID desktop) e salvalo in questa cartella.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Salva le credenziali per la prossima volta
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"[-] Errore nell'inizializzazione del servizio Google Calendar: {e}")
        return None

def fetch_google_events(days=2):
    events_list = []
    service = get_google_calendar_service()
    if not service:
        return events_list

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    time_max = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).isoformat() + 'Z'
    
    print("[*] Recupero eventi da Google Calendar...")
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Estrai descrizione e dettagli contatti se presenti
            desc = event.get('description', '')
            summary = event.get('summary', 'Senza Titolo')
            
            # Ricerca numero di telefono o email nel corpo dell'evento
            attendees = [a.get('email') for a in event.get('attendees', []) if a.get('email')]
            
            events_list.append({
                "source": "Google Calendar",
                "id": event['id'],
                "title": summary,
                "start": start,
                "end": end,
                "description": desc,
                "attendees": attendees
            })
    except Exception as e:
        print(f"[-] Errore nel caricamento eventi da Google Calendar: {e}")
        
    return events_list

def add_google_event(title, start_time, end_time, description="", attendees=None):
    service = get_google_calendar_service()
    if not service:
        print("[-] Impossibile inserire evento su Google Calendar (servizio non configurato).")
        return False
        
    event_body = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat() if isinstance(start_time, datetime.datetime) else start_time,
            'timeZone': 'Europe/Rome',
        },
        'end': {
            'dateTime': end_time.isoformat() if isinstance(end_time, datetime.datetime) else end_time,
            'timeZone': 'Europe/Rome',
        }
    }
    
    if attendees:
        event_body['attendees'] = [{'email': email} for email in attendees]
        
    try:
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        print(f"[+] Evento creato su Google Calendar: {event.get('htmlLink')}")
        return True
    except Exception as e:
        print(f"[-] Errore durante l'inserimento dell'evento su Google Calendar: {e}")
        return False


# -------------------------------------------------------------
# OUTLOOK CALENDAR HELPER
# -------------------------------------------------------------
def get_outlook_account():
    client_id = os.getenv("OUTLOOK_CLIENT_ID")
    client_secret = os.getenv("OUTLOOK_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("[-] Outlook Calendar: Credenziali OUTLOOK_CLIENT_ID o OUTLOOK_CLIENT_SECRET non configurate nel file .env.")
        return None
        
    credentials = (client_id, client_secret)
    account = Account(credentials)
    
    if not account.is_authenticated:
        # Avvia autenticazione console per l'utente
        print("[*] Avvio autenticazione per Outlook Calendar...")
        # L'autenticazione richiederà all'utente di visitare un link e incollare la URL finale di reindirizzamento
        account.authenticate(scopes=['calendar_all'])
        
    return account

def fetch_outlook_events(days=2):
    events_list = []
    account = get_outlook_account()
    if not account:
        return events_list
        
    print("[*] Recupero eventi da Outlook Calendar...")
    try:
        schedule = account.schedule()
        calendar = schedule.get_default_calendar()
        
        q = calendar.new_query()
        start = datetime.datetime.now()
        end = start + datetime.timedelta(days=days)
        q.between(start, end)
        
        events = calendar.get_events(query=q, order_by='start/dateTime')
        
        for event in events:
            # Converte le date in stringhe ISO
            start_str = event.start.isoformat() if event.start else ""
            end_str = event.end.isoformat() if event.end else ""
            
            attendees = [a.address for a in event.attendees if a.address]
            
            events_list.append({
                "source": "Outlook Calendar",
                "id": event.object_id,
                "title": event.subject,
                "start": start_str,
                "end": end_str,
                "description": event.body,
                "attendees": attendees
            })
    except Exception as e:
        print(f"[-] Errore nel caricamento eventi da Outlook Calendar: {e}")
        
    return events_list

def add_outlook_event(title, start_time, end_time, description="", attendees=None):
    account = get_outlook_account()
    if not account:
        print("[-] Impossibile inserire evento su Outlook Calendar (servizio non configurato).")
        return False
        
    try:
        schedule = account.schedule()
        calendar = schedule.get_default_calendar()
        event = calendar.new_event()
        event.subject = title
        event.body = description
        event.start = start_time
        event.end = end_time
        
        if attendees:
            for email in attendees:
                event.attendees.add(email)
                
        event.save()
        print(f"[+] Evento creato su Outlook Calendar: {title}")
        return True
    except Exception as e:
        print(f"[-] Errore durante l'inserimento dell'evento su Outlook Calendar: {e}")
        return False


# -------------------------------------------------------------
# INTERFACCIA UNIFICATA
# -------------------------------------------------------------
def get_all_upcoming_events(days=2):
    all_events = []
    
    # Carica Google Calendar
    try:
        all_events.extend(fetch_google_events(days))
    except Exception as e:
        print(f"[-] Errore generale Google Calendar: {e}")
        
    # Carica Outlook Calendar
    try:
        all_events.extend(fetch_outlook_events(days))
    except Exception as e:
        print(f"[-] Errore generale Outlook Calendar: {e}")
        
    return all_events

def get_desktop_path():
    # Salva i report direttamente nella cartella lucaai
    return r"C:\od\OneDrive - NEXTERRA SRL\Desktop\lucaai"

if __name__ == "__main__":
    # Test veloce
    import dotenv
    dotenv.load_dotenv()
    print("--- Test Lettura Agende ---")
    events = get_all_upcoming_events(days=2)
    print(f"\n=== Totale eventi trovati: {len(events)} ===")
    for ev in events:
        print(f"[{ev['source']}] {ev['title']} (Inizio: {ev['start']})")

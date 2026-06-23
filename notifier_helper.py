import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
import webbrowser

def send_email_notification(to_email, subject, body_text, body_html=None, from_email=None):
    """Invia una e-mail di promemoria tramite il server SMTP configurato nel .env o associato al mittente."""
    smtp_server = None
    smtp_port = None
    sender_email = None
    sender_password = None
    
    # Se from_email è impostato, proviamo ad abbinarlo a uno dei 4 account configurati
    if from_email:
        from_email_clean = from_email.strip().lower()
        for i in range(1, 5):
            addr = os.getenv(f"EMAIL_{i}_ADDRESS")
            if addr and addr.strip().lower() == from_email_clean:
                sender_email = addr
                sender_password = os.getenv(f"EMAIL_{i}_PASSWORD")
                smtp_server = os.getenv(f"EMAIL_{i}_SMTP_SERVER")
                smtp_port = os.getenv(f"EMAIL_{i}_SMTP_PORT")
                
                # Se il server SMTP specifico non è impostato, proviamo ad indovinarlo
                if not smtp_server:
                    imap_server = os.getenv(f"EMAIL_{i}_IMAP_SERVER", "")
                    if "gmail.com" in imap_server or "gmail.com" in from_email_clean:
                        smtp_server = "smtp.gmail.com"
                        smtp_port = "587"
                    elif "office365.com" in imap_server or "outlook.com" in from_email_clean or "hotmail.com" in from_email_clean:
                        smtp_server = "smtp.office365.com"
                        smtp_port = "587"
                    elif imap_server.startswith("imap."):
                        smtp_server = imap_server.replace("imap.", "smtp.", 1)
                        smtp_port = "587"
                break

    # Fallback su impostazioni SMTP globali o sul primo account configurato
    if not sender_email or not sender_password:
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = os.getenv("SMTP_PORT")
        sender_email = os.getenv("SMTP_SENDER_EMAIL")
        sender_password = os.getenv("SMTP_SENDER_PASSWORD")
        
        # Se anche l'SMTP globale non è configurato, usa l'Account 1 come default
        if not sender_email or not sender_password:
            sender_email = os.getenv("EMAIL_1_ADDRESS")
            sender_password = os.getenv("EMAIL_1_PASSWORD")
            smtp_server = os.getenv("EMAIL_1_SMTP_SERVER")
            smtp_port = os.getenv("EMAIL_1_SMTP_PORT")
            
            # Se l'account 1 non ha un server SMTP esplicito, indovinalo
            if sender_email and not smtp_server:
                imap_server = os.getenv("EMAIL_1_IMAP_SERVER", "")
                if "gmail.com" in imap_server or "gmail.com" in sender_email:
                    smtp_server = "smtp.gmail.com"
                    smtp_port = "587"
                elif "office365.com" in imap_server or "outlook.com" in sender_email or "hotmail.com" in sender_email:
                    smtp_server = "smtp.office365.com"
                    smtp_port = "587"
                elif imap_server.startswith("imap."):
                    smtp_server = imap_server.replace("imap.", "smtp.", 1)
                    smtp_port = "587"

    if not smtp_server or not sender_email or not sender_password:
        print(f"[-] Promemoria Email: Credenziali SMTP non configurate per {from_email or 'default'}. Salto invio a {to_email}.")
        print(f"    [Contenuto Email]: Oggetto: {subject} | Testo: {body_text}")
        return False
        
    try:
        port = int(smtp_port) if smtp_port else 587
        print(f"[*] Invio e-mail a {to_email} da {sender_email} via SMTP ({smtp_server}:{port})...")
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        
        part1 = MIMEText(body_text, "plain", "utf-8")
        msg.attach(part1)
        
        if body_html:
            part2 = MIMEText(body_html, "html", "utf-8")
            msg.attach(part2)
            
        # Connessione al server SMTP
        server = smtplib.SMTP(smtp_server, port)
        server.starttls() # Abilita cifratura TLS
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        
        print(f"[+] E-mail di promemoria inviata con successo da {sender_email} a {to_email}!")
        return True
    except Exception as e:
        print(f"[-] Errore durante l'invio dell'e-mail da {sender_email}: {e}")
        return False

def send_whatsapp_message(phone_number, message_text):
    """Genera e apre nel browser un link precompilato WhatsApp (click-to-chat) per l'invio locale."""
    # Rimuovi caratteri non numerici dal numero di telefono (mantenendo l'eventuale prefisso +)
    clean_phone = "".join([c for c in phone_number if c.isdigit() or c == '+'])
    if not clean_phone.startswith('+'):
        # Assumi prefisso italiano (+39) se non specificato
        if len(clean_phone) == 10: # Lunghezza classica cellulare italiano
            clean_phone = "+39" + clean_phone
            
    encoded_text = urllib.parse.quote(message_text)
    # URL ufficiale click-to-chat di WhatsApp
    wa_url = f"https://wa.me/{clean_phone}?text={encoded_text}"
    
    print(f"\n[*] Promemoria WhatsApp pronto per {clean_phone}!")
    print(f"    [Messaggio]: \"{message_text}\"")
    print(f"    [Link d'invio]: {wa_url}")
    
    try:
        # Apre automaticamente il browser dell'utente
        webbrowser.open(wa_url)
        print("[+] Ho aperto WhatsApp Web nel tuo browser con il messaggio precompilato. Devi solo cliccare su 'Invia'.")
        return True
    except Exception as e:
        print(f"[-] Errore nell'apertura del browser: {e}")
        return False

if __name__ == "__main__":
    # Test locale
    import dotenv
    dotenv.load_dotenv()
    print("--- Test Notifiche ---")
    # send_whatsapp_message("+393331234567", "Ciao! Questo è un promemoria di test per il nostro appuntamento di domani.")

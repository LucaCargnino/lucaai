import imaplib
import email
from email.header import decode_header
import os
from html.parser import HTMLParser

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
    def handle_data(self, d):
        self.text.append(d)
    def get_data(self):
        return ''.join(self.text)

def strip_html_tags(html_content):
    try:
        stripper = HTMLStripper()
        stripper.feed(html_content)
        return stripper.get_data()
    except Exception:
        return html_content

def decode_mime_words(s):
    if not s:
        return ""
    try:
        decoded_fragments = decode_header(s)
        decoded_string = ""
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                if encoding:
                    decoded_string += fragment.decode(encoding, errors="replace")
                else:
                    decoded_string += fragment.decode("utf-8", errors="replace")
            else:
                decoded_string += fragment
        return decoded_string
    except Exception:
        return s

def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode(errors="replace")
            elif content_type == "text/html" and "attachment" not in content_disposition:
                # Se non c'è testo semplice, salviamo l'HTML e lo puliremo dopo
                payload = part.get_payload(decode=True)
                if payload and not body:
                    body += strip_html_tags(payload.decode(errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(errors="replace")
            if msg.get_content_type() == "text/html":
                body = strip_html_tags(body)
    return body.strip()

def fetch_unread_emails(imap_server, email_address, password):
    emails_list = []
    if not imap_server or not email_address or not password:
        print(f"[-] Configurazione mancante per l'account {email_address or 'Sconosciuto'}.")
        return emails_list

    if "il_tuo_indirizzo" in email_address or "tua_password" in password:
        print(f"[-] Le credenziali per {email_address} sembrano essere valori di esempio. Salto l'account.")
        return emails_list

    print(f"[*] Connessione a {imap_server} per {email_address}...")
    try:
        # Connessione SSL
        mail = imaplib.IMAP4_SSL(imap_server, 993)
        mail.login(email_address, password)
        mail.select("inbox")

        # Cerca email non lette (UNSEEN - standard RFC 3501)
        status, response = mail.search(None, "UNSEEN")
        if status != "OK":
            print(f"[-] Errore nella ricerca di email non lette per {email_address}")
            return emails_list

        mail_ids = response[0].split()
        print(f"[+] Trovate {len(mail_ids)} email non lette per {email_address}.")

        for mail_id in mail_ids:
            status, data = mail.fetch(mail_id, "(RFC822)")
            if status != "OK":
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Estrai intestazioni
            subject = decode_mime_words(msg.get("Subject"))
            sender = decode_mime_words(msg.get("From"))
            date = decode_mime_words(msg.get("Date"))
            body = get_email_body(msg)

            # Limita la lunghezza del corpo per evitare di intasare il contesto dell'LLM
            if len(body) > 3000:
                body = body[:3000] + "\n...[Testo troncato per lunghezza]..."

            emails_list.append({
                "account": email_address,
                "sender": sender,
                "subject": subject,
                "date": date,
                "body": body
            })

        mail.logout()
    except Exception as e:
        print(f"[-] Errore di connessione o autenticazione per {email_address}: {e}")
        print("Suggerimento: Se usi Gmail/Outlook, verifica di aver abilitato IMAP e di usare una 'Password per le app'.")

    return emails_list

def get_all_accounts_emails():
    # Carica le email da tutti gli account configurati nel .env (fino a 4)
    emails = []
    for i in range(1, 5):
        server = os.getenv(f"EMAIL_{i}_IMAP_SERVER")
        addr = os.getenv(f"EMAIL_{i}_ADDRESS")
        pwd = os.getenv(f"EMAIL_{i}_PASSWORD")
        if addr and pwd:
            emails.extend(fetch_unread_emails(server, addr, pwd))
    return emails

if __name__ == "__main__":
    # Test rapido di lettura
    from dotenv import load_dotenv
    load_dotenv()
    print("--- Avvio Test Lettura Email ---")
    emails = get_all_accounts_emails()
    print(f"=== Totale email lette: {len(emails)} ===")
    for idx, em in enumerate(emails, 1):
        print(f"\n[{idx}] Da: {em['sender']}\nOggetto: {em['subject']}\nContenuto: {em['body'][:100]}...")

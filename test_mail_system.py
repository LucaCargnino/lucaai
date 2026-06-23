import os
from dotenv import load_dotenv
import email_helper
import notifier_helper

load_dotenv()

print("=== TEST RICEZIONE EMAIL ===")
try:
    emails = email_helper.get_all_accounts_emails()
    print(f"Totale email lette: {len(emails)}")
    for i, em in enumerate(emails, 1):
        print(f"[{i}] Mittente: {em['sender']} | Oggetto: {em['subject']} | Ricevuto su: {em['account']}")
except Exception as e:
    print(f"[-] Errore durante la lettura delle email: {e}")

print("\n=== TEST INVIO EMAIL ===")
# Prova ad inviare un email a se stesso da ciascun account attivo
for idx in range(1, 5):
    addr = os.getenv(f"EMAIL_{idx}_ADDRESS")
    if addr:
        print(f"\nInvio email di test da Account {idx} ({addr})...")
        success = notifier_helper.send_email_notification(
            to_email=addr,
            subject=f"Luca AI Test Invio Account {idx}",
            body_text=f"Ciao! Questo è un test per verificare le credenziali SMTP dell'Account {idx}.",
            from_email=addr
        )
        if success:
            print(f"[+] Successo: Email inviata da Account {idx} a se stesso!")
        else:
            print(f"[-] Errore: Invio da Account {idx} fallito.")

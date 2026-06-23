import os
import sys
import queue
import sounddevice as sd
import soundfile as sf
import numpy as np
import speech_recognition as sr

def check_microphone_available():
    try:
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        if not input_devices:
            return False
        return True
    except Exception:
        return False

def record_meeting_audio(filename="temp_meeting.wav", fs=44100):
    """Registra l'audio dal microfono indefinitamente finché l'utente non preme Invio."""
    if not check_microphone_available():
        print("\n[-] ERRORE: Nessun dispositivo di input audio (microfono) rilevato su questo PC.")
        return False

    q = queue.Queue()

    def callback(indata, frames, time, status):
        """Questa callback viene invocata per ogni blocco di dati audio inseriti."""
        if status:
            print(status, file=sys.stderr)
        q.put(indata.copy())

    print("\n" + "="*50)
    print(" [*] REGISTRAZIONE RIUNIONE AVVIATA")
    print("     L'agente sta registrando dal tuo microfono...")
    print("     Premi [INVIO] per terminare la registrazione.")
    print("="*50 + "\n")
    
    try:
        # Avvia lo stream audio
        with sd.InputStream(samplerate=fs, channels=1, callback=callback, dtype='int16'):
            input() # Rimane in attesa che l'utente prema Invio nel terminale
            
        # Raccoglie tutti i pezzi registrati
        audio_blocks = []
        while not q.empty():
            audio_blocks.append(q.get())

        if audio_blocks:
            recording = np.concatenate(audio_blocks, axis=0)
            sf.write(filename, recording, fs)
            print(f"[+] Registrazione completata! Audio salvato in: {filename}")
            return True
        else:
            print("[-] Nessun dato audio registrato.")
            return False
            
    except Exception as e:
        print(f"[-] Errore durante la registrazione audio: {e}")
        return False

def transcribe_audio_file(filename="temp_meeting.wav"):
    """Trascrive il file audio WAV usando Google Speech Recognition (Italiano)."""
    if not os.path.exists(filename):
        print(f"[-] Errore: Il file {filename} non esiste.")
        return ""
        
    print("[*] Avvio trascrizione dell'audio (Speech-to-Text)...")
    recognizer = sr.Recognizer()
    
    try:
        with sr.AudioFile(filename) as source:
            # Regola il rumore di fondo
            print("[*] Analisi rumore di fondo...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("[*] Lettura file audio...")
            audio_data = recognizer.record(source)
            
        print("[*] Richiesta trascrizione a Google Speech Recognition (it-IT)...")
        text = recognizer.recognize_google(audio_data, language="it-IT")
        print("[+] Trascrizione completata con successo!")
        return text
        
    except sr.UnknownValueError:
        print("[-] Speech-to-Text: Impossibile comprendere l'audio (parole non chiare o silenzio).")
        return ""
    except sr.RequestError as e:
        print(f"[-] Speech-to-Text: Errore del servizio di trascrizione: {e}")
        return ""
    except Exception as e:
        print(f"[-] Errore imprevisto durante la trascrizione: {e}")
        return ""

def get_meeting_transcript():
    """Tenta di registrare e trascrivere. Se fallisce o non c'è microfono, consente l'inserimento manuale."""
    filename = "temp_meeting.wav"
    
    # 1. Tenta la registrazione
    success = record_meeting_audio(filename)
    
    transcript = ""
    if success:
        # 2. Tenta la trascrizione
        transcript = transcribe_audio_file(filename)
        # Rimuove il file temporaneo dopo la trascrizione
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception:
            pass
            
    # Fallback se la trascrizione è vuota o la registrazione è fallita
    if not transcript:
        print("\n" + "="*50)
        print(" [FALLBACK] INSERIMENTO MANUALE DELLA TRASCRIZIONE")
        print(" Non è stato possibile registrare o trascrivere l'audio.")
        print(" Puoi incollare qui sotto il testo della riunione (premi INVIO due volte per terminare):")
        print("="*50 + "\n")
        
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        transcript = "\n".join(lines)
        
    return transcript

if __name__ == "__main__":
    # Test locale
    print("--- Test Registratore ---")
    text = get_meeting_transcript()
    print("\n--- Risultato Trascrizione ---")
    print(text)

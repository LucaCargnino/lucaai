$TaskName = "LucaAI_Background_Agent"
$ProjectDir = "C:\od\OneDrive - NEXTERRA SRL\Desktop\lucaai"
$Pythonw = "$ProjectDir\.venv\Scripts\pythonw.exe"
$Script = "$ProjectDir\run_cron_jobs.py"

Write-Host "[*] Verifica percorsi per la task pianificata..."
if (-not (Test-Path $Pythonw)) {
    Write-Error "[-] Errore: pythonw.exe non trovato in $Pythonw."
    exit 1
}

if (-not (Test-Path $Script)) {
    Write-Error "[-] Errore: lo script $Script non esiste."
    exit 1
}

Write-Host "[*] Configurazione Azione, Trigger e Impostazioni..."
# Crea l'azione della task
$Action = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$Script`"" -WorkingDirectory $ProjectDir

# Crea il trigger (giornaliero a partire dalle 8:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At "8:00AM"

# Copia la configurazione di ripetizione da un trigger temporaneo -Once (che supporta la ripetizione a creazione)
$TempOnceTrigger = New-ScheduledTaskTrigger -Once -At "8:00AM" -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Hours 12)
$Trigger.Repetition = $TempOnceTrigger.Repetition

# Impostazioni (esegui anche a batteria, arresta se dura più di 2 ore)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Write-Host "[*] Registrazione della task in Utilità di Pianificazione..."
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Scansione automatica e-mail ed agende per Luca AI" -Force
    Write-Host "[+] TASK PIANIFICATA REGISTRATA CON SUCCESSO!"
    Write-Host "    Nome task: $TaskName"
    Write-Host "    Frequenza: Ogni ora, dalle 08:00 alle 20:00"
}
catch {
    Write-Error "[-] Errore durante la registrazione della task: $_"
}

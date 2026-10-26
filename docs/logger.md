# Registrazione diagnostica

Il logger conserva tutto il contenuto ricevuto **dalla sorgente esplicitamente
collegata all'app**, compresi i campi non riconosciuti e le risposte malformate.
Non si collega da solo ai servizi MIB3 e non ascolta automaticamente DSI, CAN o
tutti i processi dell'infotainment. Occorre ancora un accesso verificato all'unità.

## Registrare le letture

I launcher `run.ps1` e `run.sh` abilitano la registrazione della demo nella loro
cartella `logs`. PowerShell accetta anche `-LogDirectory PERCORSO`.
Il programma Java diretto abilita i log solo quando si passa `--log-dir`.

Esempi dalla cartella del repository, con Java 8+ nel PATH:

```text
java -jar dist/hello-gte/hello-gte.jar --demo --watch --count 5 --log-dir logs/prova
java -jar dist/hello-gte/hello-gte.jar --file snapshot.json --watch --log-dir logs/file
java -jar dist/hello-gte/hello-gte.jar --url http://127.0.0.1:8765/snapshot --watch --log-dir logs/sorgente
```

L'URL è un esempio di adattatore locale, non un endpoint MIB3 già individuato.
Senza `--watch` o `--window` si registra una sola lettura. `--count N` termina
il polling dopo N letture; senza `--count` continua fino all'interruzione.
L'intervallo predefinito è 2 secondi, modificabile con `--interval-ms 100..60000`.
Gli errori della sorgente vengono registrati e il polling continua; un errore
di scrittura del log ferma l'acquisizione e viene mostrato nella console/finestra.

Ogni avvio crea file UTF-8 **JSON Lines**, una riga JSON per evento. Il nome
contiene ora UTC, UUID della sessione e numero progressivo della parte. Viene
stampato su stderr; stdout resta utilizzabile per l'uscita JSON dell'app.
Si aprono nuovi file senza sovrascrivere sessioni esistenti.

| Evento | Contenuto |
|---|---|
| `session_start` | Ambito acquisizione, JVM/OS che eseguono il programma, configurazione segnali e limiti |
| `source_read` | Ora iniziale/finale, durata monotona, trasporto, stato e header HTTP, fase raggiunta, tipo/dettaglio errore, corpo originale e valori interpretati |
| `stream_chunk` | Byte forniti allo standard input, senza interpretare uno schema veicolo |
| `stream_eof` | Fine normale dello standard input e totale byte acquisiti |
| `session_end` | Chiusura del logger, anche tramite shutdown hook quando possibile |
| `session_limit_reached` | Quota raggiunta, acquisizione fermata e dimensione dell'evento non salvato |

`response.content` conserva il corpo originale come testo UTF-8 valido oppure
Base64 per byte non UTF-8. `encoding` indica come ricostruirlo. Si salvano anche
SHA-256, dimensione acquisita, completamento e troncamento. I campi sconosciuti
non vengono eliminati: restano nel corpo originale anche se lo snapshot non
rispetta lo schema di Hello GTE. Si registrano anche i corpi degli errori HTTP.
Gli header e i contenuti sono salvati senza redazione automatica: possono contenere
identificatori, posizione o token della sorgente. I log rimangono nel percorso scelto.

### Limiti espliciti

- Ogni risposta file/HTTP è limitata a **256 KiB**; un corpo maggiore viene
  conservato fino al limite e marcato `truncated: true`, `complete: false`.
- Ogni file di sessione arriva a un massimo di **4 MiB**, poi prosegue nella parte successiva.
- La quota complessiva predefinita è **32 MiB per sessione**, inclusi struttura e
  codifica. `--log-max-mib N` la cambia (1..1024). Si riserva spazio all'evento finale
  di limite e si ferma l'acquisizione; la singola lettura che eccede la quota non è salvata.
- La quota è per sessione: i file delle sessioni precedenti restano al loro posto.
- I byte sono scaricati nel file dopo ogni evento. La chiusura forzata del processo
  potrebbe non produrre `session_end`; il lettore segnala anche le sequenze mancanti.

## Acquisire messaggi da una console o da un altro esportatore

La modalità seguente registra tutti i byte ricevuti su stdin, senza richiedere
JSON. La si può collegare all'uscita di un lettore di log o a uno stream esportato
dal MIB3, **dopo aver ottenuto accesso a quella sorgente**:

```text
java -jar dist/hello-gte/hello-gte.jar --capture-stdin --log-dir logs/console
```

`--capture-stdin` attende dati o EOF. Non esegue comandi sul dispositivo, non
apre porte e non scopre servizi. Lo stream viene registrato a blocchi di 8 KiB;
un messaggio può attraversare più blocchi. La concatenazione recupera i byte
originali, anche se un carattere UTF-8 cade al confine tra due blocchi.

## Rileggere e recuperare i contenuti

Con Python 3.10+:

```text
python tools/read_log.py logs/prova
python tools/read_log.py logs/prova --fields
python tools/read_log.py logs/console --extract build/console-recuperata
```

Il riepilogo mostra eventi, codici HTTP, errori, byte, risposte parziali e buchi
di sequenza. `--fields` elenca i percorsi JSON realmente presenti nei corpi,
anche quando non esistono nella configurazione dell'app. Non stampa i valori.
`--extract` verifica SHA-256 e lunghezza, poi ricrea risposte `.bin` e lo stream
concatenato `stream.bin` in sottocartelle per sessione. I file sono creati in
modo esclusivo: usare una nuova destinazione per ripetere un'estrazione.

Questi log ci aiuteranno a identificare disponibilità, nomi, unità e tempi dei
segnali GTE. Da soli non forniscono accesso o installazione sul MIB3 1989.

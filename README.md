# Hello GTE

Primo prototipo: **Ciao mondo** e sei parametri della Golf 8 GTE. Include un programma
Java con uscita testuale/JSON e un'anteprima grafica desktop.

**Stato: prototipo per PC/laboratorio. L'installazione sul MIB3 e la lettura diretta
dei segnali del veicolo non sono implementate. L'archivio ZIP non è flashabile.**

Target ricavato dalla foto: unità **5H0035816G**, hardware **H56**, software **1989**.
Questi sono dati di riferimento, non letture effettuate dal programma. La sigla
completa del firmware e i servizi disponibili sulla specifica unità restano da verificare.

## Prova rapida su Windows

La distribuzione compilata è in `dist/hello-gte/`; l'archivio completo è
`dist/hello-gte-desktop-lab.zip`. Per la demo con finestra:

```powershell
.\run.ps1
```

Il launcher cerca Java in `JAVA_HOME`, nel PATH e nell'installazione di Android Studio.
Si può indicare un eseguibile con `-JavaPath`. Per la stampa testuale:

```powershell
.\run.ps1 -Console
```

I launcher creano anche una sessione diagnostica in `logs/`, registrando ciò che
la sorgente restituisce. Dettagli, acquisizione stream ed estrazione dei dati:
[logger diagnostico](docs/logger.md).

Su Linux/macOS con Java 8+ è disponibile `sh run.sh`. La finestra usa Swing ed è
un'anteprima PC: la visualizzazione nativa sull'infotainment richiede un'integrazione HMI separata.

## Parametri previsti

| Campo del prototipo | Unità | Campione demo |
|---|---|---|
| Stato di carica batteria GTE | % | 64 |
| Autonomia elettrica | km | 31 |
| Velocità | km/h | 0 |
| Temperatura refrigerante | °C | 76 |
| Temperatura batteria HV | °C | Non disponibile |
| Potenza di ricarica | kW | 0,0 |

I numeri sono inventati per la demo. La disponibilità di ciascun segnale sul MIB3
1989 non è dimostrata; alcuni potrebbero richiedere una sorgente diagnostica distinta.

## Collegare dati esterni

Il lettore accetta uno **snapshot JSON nel formato del prototipo**, da file oppure
da un endpoint HTTP(S) esplicitamente fornito. Le chiavi JSON non sono identificatori
VW/DSI/RSI. Non esiste un indirizzo del MIB3 preconfigurato: serve un adattatore che
acquisisca e normalizzi i dati reali. Vedere [schema e stati](docs/schema-dati.md).

Esempi da terminale, usando il proprio `java` oppure il percorso completo all'eseguibile:

```text
java -jar dist/hello-gte/hello-gte.jar --demo
java -jar dist/hello-gte/hello-gte.jar --demo --window
java -jar dist/hello-gte/hello-gte.jar --demo --json
java -jar dist/hello-gte/hello-gte.jar --file mio-snapshot.json --window
java -jar dist/hello-gte/hello-gte.jar --url http://127.0.0.1:8765/snapshot --json
java -jar dist/hello-gte/hello-gte.jar --file mio-snapshot.json --watch
java "-Djava.awt.headless=true" -jar dist/hello-gte/hello-gte.jar --demo --render build/anteprima.png
```

L'URL dell'esempio è un ipotetico adattatore locale da realizzare, non una API VW.
Le letture HTTP usano solo GET, con timeout e senza seguire redirect. Non c'è scansione
di rete. Un errore svuota i valori; non attiva la demo. `simulation: true` rimane
visibile anche importando il campione da file/HTTP. Un dato senza timestamp non viene
presentato come recente; oltre 15 secondi viene indicato come precedente.

## Compilazione e verifica

Dal repository sorgente, richiede Python 3.10+ e JDK 9+ per compilare.
L'output usa bytecode Java 8. Lo ZIP contiene la distribuzione eseguibile e le istruzioni.
La build scarica Gson 2.14.0 da Maven Central e verifica il digest SHA-256 fissato
in `tools/build.py`; include la licenza Apache-2.0 nella distribuzione.

```text
python tools/build.py
python tools/build.py --jdk PERCORSO_JDK
python -m unittest discover -s tests -v
```

I test eseguono il JAR e un server locale controllato, verificando letture, unità,
timestamp, dati mancanti, errori HTTP e assenza di richieste di scrittura.
Non verificano la compatibilità con una vera unità MIB3.

## Passaggio all'infotainment

Per il primo tentativo sul sistema reale c'è ora una sonda separata, senza Java:
[sonda Ciao mondo](probe/README.md). Il pacchetto `dist/mib3-hello-probe.zip`
contiene uno script `sh` che crea `hello.txt` con informazioni essenziali del sistema.
Richiede una shell o un launcher già disponibile: non include un metodo di accesso
e non parte automaticamente inserendo la chiavetta. Per ricrearlo basta
`python tools/package_probe.py`, senza compilatore o download.

Disponendo di OBDeleven/VCDS, il prossimo passo sulla Golf è la
[lettura dell'identificazione 5F](docs/identificazione-5f.md), per confermare
famiglia hardware e versione completa prima di scegliere una procedura di accesso.

La scelta Java nasce dalla presenza di OpenJDK 8 descritta in analisi pubbliche di
firmware MOI3 LG. Non dimostra che il JAR sia avviabile sulla tua versione.
Per procedere servono un accesso verificato, la mappatura dei segnali e l'integrazione
con il display. Il percorso mappe/aggiornamenti è ancora una pista di ricerca:
non è stato individuato un installatore funzionante per H56/1989.

Riferimenti e punti aperti: [accesso MIB3](docs/accesso-mib3.md).

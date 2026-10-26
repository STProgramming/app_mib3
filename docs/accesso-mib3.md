# Accesso MIB3: evidenze e punti aperti

Ricerca aggiornata al 20 ottobre 2026. Nessun collegamento a un veicolo è stato
effettuato. Il codice del prototipo e della sonda è verificato soltanto su PC.

## Ciò che sappiamo

La foto fornita mostra unità `5H0035816G`, HW `H56`, SW `1989`; il display riporta
HW `H46`, SW `2092`. Il nome completo del firmware non compare nella foto.

Analisi indipendenti di firmware MOI3 LG descrivono AGL/Linux, una JVM OpenJDK 8 e
una HMI Java con librerie native dedicate al display. Descrivono anche servizi
`DSICar*` che arrivano alla HMI da `carifservice` e un bus RSI/VIWI distinto.
Questo rende ragionevole un candidato console Java 8, ma non prova la compatibilità
di runtime, accesso e grafica sul software 1989. Le versioni analizzate dalla fonte
non sono il 1989. Non assumiamo che tutti i valori GTE siano esposti in RSI/HTTP.

Fonti primarie delle analisi (non documentazione ufficiale VW):

- [Struttura firmware e JVM](https://github.com/lipedesign/mib3-moi3-lg-research/blob/main/docs/firmware.md)
- [HMI e servizi veicolo, sezioni 4–5](https://github.com/lipedesign/mib3-moi3-lg-research/blob/main/docs/hmi.md)
- [Esperimenti grafici su banco PC](https://github.com/lipedesign/moi3-cluster-pipeline-re)

## Pista mappe/aggiornamenti

Volkswagen documenta l'importazione automatica di mappe via USB. Un validatore
pubblico mostra come leggere `PACKAGE.SLIST`, configurazioni e checksum. Il suo
codice non riproduce l'intera verifica del dispositivo e non è un generatore di
pacchetti autorizzati. Il controllo degli hash su PC non dimostra l'accettazione
di un pacchetto modificato da parte del MIB3.

- [Manuale ufficiale Discover Pro Gen.3, novembre 2020](https://app-connect.volkswagen.com/mapupdates/manuals/Discover_Pro_Gen.3_November_2020.pdf)
- [Validatore mappe e sorgente](https://github.com/pschlan/vw-mib3-map-validator)

Non abbiamo ispezionato l'importatore del firmware 1989 né dimostrato esecuzione
di codice tramite un aggiornamento mappe. I pacchetti firmware firmati e i dati
mappa sono percorsi da analizzare separatamente. Il JAR e lo ZIP prodotti qui
sono artefatti per laboratorio, da non presentare come aggiornamenti mappe.

## Pista USB / menu di manutenzione REM

Il 23 agosto 2025 l'autore jugih descrive accesso alla propria MOI3 LG tramite
console UART oppure tramite REM con script bash, in forma semi-interattiva.
Pubblica anche mount Linux, tra cui `/tmp` su tmpfs e una chiavetta in
`/tmp/USB/PORT1/PART1`, e nomi di attributi hardware sotto
`/sys/devices/soc/soc:common_gpio_default`. Questo è un resoconto primario utile
a motivare una sonda `sh`. Il post non pubblica la ricetta per avviare uno script
personalizzato dal REM e non dimostra compatibilità con H56 / SW 1989.

- [Resoconto MOI3 LG, UART/REM, mount e attributi hardware](https://keskustelu.vagtech.fi/threads/mib3oi-eli-moi3-lg-syvallisemmin.533/)

La pagina commerciale MIB Ultimate elenca, per il modulo LG MOI3 + Preh, operazioni
via USB e accesso SSH/Telnet. Separatamente dichiara una soluzione di downgrade
per la disattivazione della protezione componenti anche sulle versioni 1989/1990.
Sono dichiarazioni del fornitore: non abbiamo verificato il prodotto, le condizioni
di accesso shell sul 1989 o la compatibilità con `5H0035816G`. La presenza di una
funzione USB commerciale non fornisce il relativo metodo pubblico di avvio.
Non è stata selezionata né provata una procedura di downgrade.

- [Funzioni dichiarate dal fornitore, LG MOI3 + Preh](https://mibultimate.com/fr/purchase)

Conclusione operativa: REM/USB è una pista plausibile per arrivare a eseguire codice
temporaneo, ma non abbiamo un loader pubblico verificato per questa unità.
L'importazione mappe ordinaria non può essere trattata come se fosse già quel loader.

## Sonda pronta, accesso da dimostrare

`probe/mib3-hello.sh` crea un solo `hello.txt` in una directory scelta dall'utente.
Non richiede Java e non installa nulla. Legge informazioni di sistema limitate e
alcuni attributi hardware; non legge ancora segnali GTE. Senza `--lab` richiede
Linux ARM64 e directory coerenti con MOI3 LG, ma questo controllo non certifica
il firmware. Il report di una prova PC è marcato esplicitamente come laboratorio.

Il pacchetto `dist/mib3-hello-probe.zip` non contiene `autorun`, manifest di
aggiornamento o un report di successo precompilato. La chiamata manuale allo script
è documentata nel suo README e presuppone accesso shell già ottenuto.

Con OBDeleven/VCDS possiamo ora leggere la 5F per confermare l'identificazione:
[procedura e campi richiesti](identificazione-5f.md). L'identificazione OBD e
l'esecuzione di script Linux sono passaggi distinti; non è stato trovato un
adattamento OBD confermato che faccia da launcher sul software 1989.

## Milestone per un'app sull'unità reale

1. Confermare firmware completo, piattaforma e accesso a un runtime utilizzabile.
2. Eseguire temporaneamente il candidato console senza modificare firmware o avvio.
3. Identificare sorgenti e unità dei segnali GTE; leggere un campione reale e
   verificarne timestamp, validità e significato. Il trasporto JSON del prototipo
   è un confine per l'adattatore da sviluppare, non un servizio già trovato nel MIB3.
4. Integrare una superficie grafica con la HMI/compositor effettivamente presenti.
5. Solo dopo validare installazione, avvio e rimozione persistenti sulla versione specifica.

Stato attuale: demo, lettore generico, candidato console e sonda `sh` costruiti sul PC.
Le milestone sul veicolo sono aperte.

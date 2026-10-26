# Sonda Ciao mondo per MOI3 LG

Script POSIX `sh`, senza compilazione, Java o librerie da installare. Esegue una
sola raccolta e crea `hello.txt` nella directory esplicitamente indicata.

**Serve gia una shell o un launcher verificato. Questo pacchetto non fornisce
l'accesso al MIB3 e non e un aggiornamento flashabile. Copiarlo su USB non lo avvia.**

Target di ricerca: Golf 8 GTE 2021, unita `5H0035816G`, HW `H56`, SW `1989`.
Il funzionamento su questa unita non e ancora stato provato.

## Primo passo con OBDeleven/VCDS

Seguire [lettura identificazione 5F](../docs/identificazione-5f.md). I dati della 5F
servono a scegliere una procedura di accesso compatibile; la diagnosi OBD da sola
non fornisce il terminale usato qui sotto.

## Quando sara disponibile una shell reale

1. Estrarre lo ZIP su USB, mantenendo la cartella `mib3-hello-probe`.
2. Nella shell, leggere `cat /proc/mounts` e identificare il mount della chiavetta.
   `/tmp/USB/PORT1/PART1` e un percorso osservato su un'altra MOI3 LG: verificare
   quello effettivo prima di usarlo. Non creare a mano un mount mancante.
3. Se il mount coincide esattamente con l'esempio, eseguire:

   ```sh
   sh /tmp/USB/PORT1/PART1/mib3-hello-probe/mib3-hello.sh --output-dir /tmp/USB/PORT1/PART1
   ```

   Con un mount diverso sostituire entrambi i percorsi. `sh` legge lo script dalla
   chiavetta: non sono necessari `chmod`, copie sulla memoria interna o installazione.
4. Attendere `Creato: .../hello.txt` e la fine del comando. Usare la rimozione
   sicura del supporto disponibile sul sistema prima di scollegare la chiavetta.
5. Controllare che il report inizi con `Ciao mondo` e termini con
   `report_complete=yes`. Se il file esiste gia, la sonda si ferma: conservare il
   report precedente e rimuoverlo o spostarlo dal PC prima di una nuova prova.

Il contesto `MOI3_LG_CANDIDATE_UNVERIFIED` significa che la shell vede Linux,
ARM64 e le directory LG previste. Non certifica l'hardware, il firmware 1989,
il metodo di accesso o l'integrazione con il display.

## Contenuto del report

- Ora UTC dell'orologio del dispositivo, PID, kernel, architettura, UID/GID.
- `/etc/os-release`, uptime e informazioni memoria, con dimensioni di lettura limitate.
- Presenza di pochi percorsi runtime, senza avviarli.
- Otto attributi hardware esplicitamente selezionati, se leggibili.

La sonda legge i file sopra elencati e crea soltanto `hello.txt`. Non raccoglie
ancora parametri GTE. Non legge credenziali, identificativi di sicurezza,
rubrica, cronologia o log generici; non effettua richieste di rete, modifiche
OBD, remount, avvio di servizi o scritture alla configurazione. La shell e il
sistema ospite possono avere propri log indipendenti da questo script.

## Prova di laboratorio

Da una shell POSIX su PC, scegliere una directory esistente con percorso assoluto:

```sh
sh mib3-hello.sh --lab --output-dir /percorso/assoluto/output
```

Il report riporta sempre `LAB_NOT_VEHICLE_VERIFICATION`. E una verifica dello
script, non una dimostrazione di esecuzione nell'infotainment. Lo ZIP non contiene
un `hello.txt` precompilato.

## Ricostruire il pacchetto dal repository

```text
python tools/package_probe.py
```

Evidenze e limiti della ricerca: [accesso MIB3](../docs/accesso-mib3.md).

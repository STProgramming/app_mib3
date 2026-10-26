# Leggere l'identificazione 5F con OBDeleven o VCDS

Questa e la prossima operazione utile sulla Golf: acquisire l'identificazione della
centralina infotainment senza cambiare adattamenti o codifica. Eseguire la lettura
ad auto ferma, quadro acceso; il motore non serve per l'identificazione.

## OBDeleven

1. Collegare il dispositivo e aprire la propria auto nell'app.
2. Aprire **Centraline / Control units** e scegliere **5F - Multimedia / Information electronics**.
3. Aprire **Informazioni centralina / Control unit information** e annotare i dati elencati sotto.
4. Se disponibile, aprire **Identificazione avanzata / Advanced identification**;
   leggere i campi software/hardware pertinenti. La disponibilita dei singoli
   campi dipende dalla centralina e dalla versione dell'app.

Documentazione ufficiale: [informazioni centralina](https://obdeleven.com/features/control-unit-information),
[identificazione avanzata UDS](https://support.obdeleven.com/en/articles/5608798-advanced-identification-uds).

## VCDS

1. Collegare l'interfaccia e accendere il quadro.
2. Aprire **Select / Seleziona -> 5F - Information Electr.**
3. Conservare le informazioni mostrate nella schermata della centralina.
4. Aprire **Advanced ID - 1A** se disponibile, poi **Save** o **Copy**. Il report
   testuale viene normalmente salvato in `C:\Ross-Tech\VCDS\Logs`.

Documentazione ufficiale: [schermata centralina](https://www.ross-tech.com/vcds/tour/open_screen.html),
[Advanced ID](https://www.ross-tech.com/vcds/tour/advancedid.php).

## Dati che servono

```text
Strumento e versione app:
Centralina: 5F
Codice ricambio SW / Part No SW:
Codice ricambio HW / Part No HW:
Component:
Versione HW:
Versione SW:
Software train completo, se presente (esempio di prefisso: MOI3_...):
Identificativo ASAM/ODX e versione:
Eventuali campi software aggiuntivi:
```

Riportare i valori effettivi: `1989` e la sigla completa `MOI3_...` sono informazioni
distinte. Se il train non compare, indicare **non disponibile**, senza ricostruirlo
dal numero versione. VIN, numero seriale e identificativi di sicurezza non servono
per questa fase e possono essere omessi.

Queste funzioni leggono l'identita del modulo. SFD non impedisce le letture di
identificazione di base; un eventuale sblocco SFD per modifiche e una funzione
distinta. [Riferimento Ross-Tech su SFD](https://wiki.ross-tech.com/wiki/index.php/SFD).

## Cosa permette di decidere

L'identificazione serve a confermare la famiglia e confrontare un'eventuale
procedura USB/REM con l'unita reale. OBDeleven/VCDS non sono, per questo progetto,
un launcher di script Linux. Non abbiamo un adattamento verificato su H56/1989
che apra una shell. Abilitare un menu engineering da solo non dimostra tale accesso.

Il passo successivo dipendera da questi dati. Al momento non e stata selezionata
una patch o una procedura di downgrade per la tua unita.

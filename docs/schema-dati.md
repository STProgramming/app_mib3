# Contratto dati del prototipo

Questo JSON è un formato locale di Hello GTE, **non un protocollo Volkswagen**.
L'adattatore verso DSI, RSI o un lettore diagnostico non è ancora disponibile.

```json
{
  "schema_version": 1,
  "simulation": false,
  "observed_at": "2026-10-20T12:00:00Z",
  "signals": {
    "battery_soc": {"value": 64, "unit": "%"},
    "electric_range": {"value": 31, "unit": "km"},
    "speed": {"value": 0, "unit": "km/h"},
    "coolant_temperature": {"value": 76, "unit": "°C"},
    "battery_temperature": {"value": null, "unit": "°C"},
    "charging_power": {"value": 0.0, "unit": "kW"}
  }
}
```

Anche questi numeri sono un esempio. `simulation: false` descrive ciò che dichiara
la sorgente, non autentica la provenienza dal veicolo. La UI indica sempre che
l'origine esterna non è verificata.

- `schema_version`: numero 1; `simulation`: booleano obbligatorio.
- `observed_at`: momento effettivo di acquisizione, ISO-8601 con fuso. Il lettore
  non lo sostituisce con l'ora del download. Se assente/null, l'età è sconosciuta.
- Ogni segnale contiene un numero JSON finito e l'unità esatta. Stringhe numeriche,
  unità diverse e valori fuori dai limiti configurati diventano `invalid`.
- Un segnale assente o con `value: null` diventa `unavailable`, non zero.
- Un timestamp oltre 15 secondi nel passato è `stale`; oltre 5 secondi nel futuro
  è `future_timestamp`. Il valore resta visibile attenuato e con il relativo stato.
- La carica è la percentuale della batteria di trazione; il refrigerante non è la
  temperatura dell'olio; la potenza di ricarica è positiva in ingresso. Eventuali
  conversioni di scala/segno si fanno nell'adattatore, sulla base di segnali verificati.

`config/signals.json` contiene etichette, unità, limiti di plausibilità e percorsi
JSON Pointer RFC 6901. I limiti non sono specifiche ufficiali della Golf.
`--config` permette di usare una configurazione alternativa di sei campi.
Il percorso individua un oggetto `{value, unit}`, anche dentro un array; `~1` e
`~0` rappresentano `/` e `~` nei nomi delle proprietà.

Il trasporto HTTP usa GET verso un singolo URL HTTP(S), senza credenziali nel URL,
con timeout di connessione/lettura di 1,5 secondi e risposta limitata a 256 KiB.
I redirect sono restituiti come errori; TLS usa la verifica standard della JVM.
Il polling della finestra/testo è ogni 2 secondi. L'uscita testuale/JSON singola
restituisce codice 1 in caso di errore della sorgente e 2 per argomenti/configurazione non validi.

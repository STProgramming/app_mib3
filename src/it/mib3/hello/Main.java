package it.mib3.hello;

import java.io.*;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

public final class Main {
    public static void main(String[] args) {
        try {
            System.setOut(new PrintStream(System.out, true, "UTF-8"));
            System.setErr(new PrintStream(System.err, true, "UTF-8"));
            int status = run(args);
            if (status != 0) System.exit(status);
        }
        catch (Exception e) {
            System.err.println("Errore: " + e.getMessage());
            System.exit(2);
        }
    }

    private static int run(String[] args) throws Exception {
        boolean demo = false, window = false, json = false, watch = false, stdin = false;
        Path file = null, config = null, render = null, logDirectory = null;
        String url = null;
        int width = 1280, height = 720, count = 0, interval = 2000, logMiB = 32;
        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            if (a.equals("--demo")) demo = true;
            else if (a.equals("--window")) window = true;
            else if (a.equals("--json")) json = true;
            else if (a.equals("--watch")) watch = true;
            else if (a.equals("--capture-stdin")) stdin = true;
            else if (a.equals("--file") && i + 1 < args.length) file = Paths.get(args[++i]);
            else if (a.equals("--config") && i + 1 < args.length) config = Paths.get(args[++i]);
            else if (a.equals("--url") && i + 1 < args.length) url = args[++i];
            else if (a.equals("--render") && i + 1 < args.length) render = Paths.get(args[++i]);
            else if (a.equals("--width") && i + 1 < args.length) width = Integer.parseInt(args[++i]);
            else if (a.equals("--height") && i + 1 < args.length) height = Integer.parseInt(args[++i]);
            else if (a.equals("--count") && i + 1 < args.length) count = Integer.parseInt(args[++i]);
            else if (a.equals("--interval-ms") && i + 1 < args.length) interval = Integer.parseInt(args[++i]);
            else if (a.equals("--log-dir") && i + 1 < args.length) logDirectory = Paths.get(args[++i]);
            else if (a.equals("--log-max-mib") && i + 1 < args.length) logMiB = Integer.parseInt(args[++i]);
            else if (a.equals("--help")) {
                System.out.println("Hello GTE · prototipo, non installatore MIB3\n"
                    + "java -jar hello-gte.jar (--demo | --file snapshot.json | --url http(s)://endpoint)\n"
                    + "  [--window | --json | --watch | --render anteprima.png] [--config signals.json]\n"
                    + "  [--width 1280 --height 720]\n"
                    + "  [--log-dir logs --log-max-mib 32] [--watch --count 10 --interval-ms 2000]\n"
                    + "Oppure: java -jar hello-gte.jar --capture-stdin --log-dir logs\n"
                    + "L'endpoint deve fornire lo schema del prototipo. Non è una API VW già collegata.");
                return 0;
            } else throw new IllegalArgumentException("Argomento sconosciuto o valore assente: " + a);
        }
        int sources = (demo ? 1 : 0) + (file == null ? 0 : 1) + (url == null ? 0 : 1) + (stdin ? 1 : 0);
        if (sources != 1) throw new IllegalArgumentException("Scegliere una sola sorgente: --demo, --file, --url o --capture-stdin");
        int outputs = (window ? 1 : 0) + (json ? 1 : 0) + (watch ? 1 : 0) + (render == null ? 0 : 1);
        if (outputs > 1) throw new IllegalArgumentException("Scegliere una sola modalità di uscita");
        if (width < 640 || width > 3840 || height < 360 || height > 2160)
            throw new IllegalArgumentException("Anteprima: larghezza 640..3840, altezza 360..2160");
        if (count < 0 || (count > 0 && !watch) || interval < 100 || interval > 60000)
            throw new IllegalArgumentException("--count richiede --watch; intervallo consentito 100..60000 ms");
        if (logMiB < 1 || logMiB > 1024 || (logMiB != 32 && logDirectory == null))
            throw new IllegalArgumentException("--log-max-mib richiede --log-dir, limite 1..1024 MiB");
        if (stdin) {
            if (logDirectory == null || outputs > 0 || config != null)
                throw new IllegalArgumentException("--capture-stdin richiede --log-dir e nessuna modalità di visualizzazione");
            try (DiagnosticLog log = startLog(logDirectory, logMiB, "stdin_bytes", Collections.emptyList())) {
                byte[] buffer = new byte[8192];
                long received = 0;
                int n;
                while ((n = System.in.read(buffer)) != -1) {
                    log.stream(Arrays.copyOf(buffer, n));
                    received += n;
                }
                log.streamEof(received);
                System.out.println("Acquisizione stream completata: " + received + " byte");
            }
            return 0;
        }
        List<Telemetry.Signal> signals = Telemetry.signals(config);
        DiagnosticLog log = startLog(logDirectory, logMiB, "explicit_source_responses", signals);
        Telemetry.Source source;
        try { source = new Telemetry.Source(demo, file, url, signals, log); }
        catch (Exception e) { if (log != null) log.close(); throw e; }
        if (window) {
            try { Dashboard.open(source); }
            catch (Exception e) { source.close(); throw e; }
            return 0;
        }
        try (Telemetry.Source active = source) {
            if (render != null) {
                Dashboard.render(active.read(), render, width, height);
                System.out.println("Anteprima PC: " + render.toAbsolutePath());
                return 0;
            }
            int readCount = 0;
            Telemetry.Frame frame;
            do {
                frame = active.read();
                if (json) System.out.println(Telemetry.asJson(frame));
                else {
                    System.out.println("Ciao mondo · Hello GTE");
                    System.out.println(frame.status(Instant.now()) + " | " + frame.source);
                    for (Telemetry.Reading r : frame.readings) {
                        System.out.println(r.signal.label + ": " + r.formatted()
                            + (r.value == null ? " (" + r.state + ")" : " " + r.signal.unit));
                    }
                    if (frame.error != null) System.out.println("Dettaglio: " + frame.error);
                    System.out.println();
                }
                readCount++;
                if (!watch || (count > 0 && readCount >= count)) break;
                Thread.sleep(interval);
            } while (true);
            return frame.error == null ? 0 : 1;
        }
    }

    private static DiagnosticLog startLog(Path directory, int maxMiB, String scope,
                                          List<Telemetry.Signal> signals) throws IOException {
        if (directory == null) return null;
        final DiagnosticLog log = new DiagnosticLog(directory, maxMiB * 1024L * 1024L, scope, signals);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try { log.close(); }
            catch (IOException e) { System.err.println("Errore chiusura logger: " + e.getMessage()); }
        }, "diagnostic-log-close"));
        System.err.println("Log sessione: " + log.firstFile());
        return log;
    }
}

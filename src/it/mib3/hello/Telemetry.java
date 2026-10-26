package it.mib3.hello;

import com.google.gson.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.*;
import java.util.*;

/** Reads an application-defined snapshot, not the proprietary VW DSI protocol. */
public final class Telemetry {
    static final int MAX_BYTES = 262144;
    static final Gson JSON = new GsonBuilder().setStrictness(Strictness.STRICT)
        .disableJdkUnsafe().serializeNulls().setPrettyPrinting().create();

    public static final class Signal {
        public String id, label, path, unit;
        public double min, max;
        public int decimals;
    }

    public static final class Reading {
        public final Signal signal;
        public final Double value;
        public final String state;
        Reading(Signal signal, Double value, String state) {
            this.signal = signal; this.value = value; this.state = state;
        }
        public String formatted() {
            return value == null ? "—" : String.format(Locale.ITALY,
                "%." + signal.decimals + "f", value);
        }
    }

    public static final class Frame {
        public final boolean simulation;
        public final String transport, source, error;
        public final Instant observedAt;
        public final List<Reading> readings;
        Frame(boolean simulation, String transport, String source, String error,
              Instant observedAt, List<Reading> readings) {
            this.simulation = simulation; this.transport = transport;
            this.source = source; this.error = error; this.observedAt = observedAt;
            this.readings = Collections.unmodifiableList(readings);
        }
        public String freshness(Instant now) {
            if (error != null) return "error";
            if (simulation) return "demo";
            if (observedAt == null) return "unknown_age";
            long millis = Duration.between(observedAt, now).toMillis();
            if (millis < -5000) return "future_timestamp";
            return millis > 15000 ? "stale" : "recent";
        }
        public String status(Instant now) {
            switch (freshness(now)) {
                case "error": return "Sorgente non disponibile";
                case "demo": return "DEMO · DATI SIMULATI";
                case "stale": return "Dati precedenti · oltre 15 secondi";
                case "future_timestamp": return "Orario sorgente non valido";
                case "unknown_age": return "Età del dato non disponibile";
                default: return "Dati ricevuti · origine non verificata";
            }
        }
    }

    static byte[] readLimited(InputStream input) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        try {
            int count;
            while ((count = input.read(buffer)) != -1) {
                int keep = Math.min(count, MAX_BYTES - out.size());
                out.write(buffer, 0, keep);
                if (keep < count) throw new CapturedReadException("Risposta oltre 256 KiB",
                    null, out.toByteArray(), true);
            }
        } catch (CapturedReadException e) { throw e; }
        catch (IOException e) {
            throw new CapturedReadException(e.getMessage(), e, out.toByteArray(), false);
        }
        return out.toByteArray();
    }

    static final class CapturedReadException extends IOException {
        private static final long serialVersionUID = 1L;
        final byte[] captured;
        final boolean truncated;
        CapturedReadException(String message, Throwable cause, byte[] captured, boolean truncated) {
            super(message, cause); this.captured = captured; this.truncated = truncated;
        }
    }

    static final class ReadTrace {
        final Instant startedAt = Instant.now();
        final long startedNanos = System.nanoTime();
        Instant finishedAt;
        long elapsedMs;
        String stage = "load", contentType, errorType, errorDetail;
        Integer httpStatus;
        Long declaredLength;
        Map<String, List<String>> httpHeaders;
        byte[] body = new byte[0];
        boolean complete, truncated;
    }

    static String readFile(Path path) throws IOException {
        try (InputStream in = Files.newInputStream(path)) {
            return new String(readLimited(in), StandardCharsets.UTF_8);
        }
    }

    static String resource(String path) throws IOException {
        try (InputStream in = Telemetry.class.getResourceAsStream(path)) {
            if (in == null) throw new IOException("Risorsa assente: " + path);
            return new String(readLimited(in), StandardCharsets.UTF_8);
        }
    }

    static List<Signal> signals(Path custom) throws IOException {
        String text = custom == null ? resource("/signals.json") : readFile(custom);
        Signal[] definitions = JSON.fromJson(text, Signal[].class);
        if (definitions == null || definitions.length != 6)
            throw new IllegalArgumentException("La configurazione deve contenere sei segnali");
        Set<String> ids = new HashSet<String>();
        for (Signal s : definitions) {
            if (s == null || s.id == null || !ids.add(s.id) || s.label == null
                    || s.unit == null || s.path == null || !s.path.startsWith("/")
                    || s.min > s.max || !Double.isFinite(s.min) || !Double.isFinite(s.max)
                    || s.decimals < 0 || s.decimals > 3)
                throw new IllegalArgumentException("Definizione segnale non valida");
        }
        return Arrays.asList(definitions);
    }

    /** RFC 6901 JSON pointer; no evaluation of expressions or commands. */
    static JsonElement pointer(JsonElement root, String path) {
        JsonElement current = root;
        for (String token : path.substring(1).split("/", -1)) {
            token = token.replace("~1", "/").replace("~0", "~");
            if (current == null || current.isJsonNull()) return JsonNull.INSTANCE;
            if (current.isJsonObject()) current = current.getAsJsonObject().get(token);
            else if (current.isJsonArray() && token.matches("0|[1-9][0-9]*")) {
                try { current = current.getAsJsonArray().get(Integer.parseInt(token)); }
                catch (RuntimeException e) { return JsonNull.INSTANCE; }
            } else return JsonNull.INSTANCE;
        }
        return current == null ? JsonNull.INSTANCE : current;
    }

    static Frame parse(String text, boolean forceDemo, String transport, String source,
                       List<Signal> signals) {
        JsonObject root = JSON.fromJson(text, JsonObject.class);
        if (root == null) throw new IllegalArgumentException("Snapshot JSON vuoto");
        JsonElement version = root.get("schema_version");
        if (version == null || !version.isJsonPrimitive()
                || !version.getAsJsonPrimitive().isNumber() || version.getAsDouble() != 1)
            throw new IllegalArgumentException("schema_version deve essere 1");
        JsonElement marker = root.get("simulation");
        if (marker == null || !marker.isJsonPrimitive() || !marker.getAsJsonPrimitive().isBoolean())
            throw new IllegalArgumentException("Indicare simulation: true oppure false");
        boolean simulation = forceDemo || marker.getAsBoolean();
        Instant timestamp = null;
        JsonElement time = root.get("observed_at");
        if (time != null && !time.isJsonNull()) {
            if (!time.isJsonPrimitive() || !time.getAsJsonPrimitive().isString())
                throw new IllegalArgumentException("observed_at deve essere una data ISO-8601");
            timestamp = Instant.parse(time.getAsString());
        }
        List<Reading> readings = new ArrayList<Reading>();
        for (Signal signal : signals) {
            JsonElement item = pointer(root, signal.path);
            Double value = null;
            String state = "unavailable";
            if (item.isJsonObject()) {
                JsonObject object = item.getAsJsonObject();
                JsonElement number = object.get("value"), unit = object.get("unit");
                if (number != null && !number.isJsonNull()) {
                    state = "invalid";
                    if (number.isJsonPrimitive() && number.getAsJsonPrimitive().isNumber()
                            && unit != null && unit.isJsonPrimitive()
                            && unit.getAsJsonPrimitive().isString()
                            && signal.unit.equals(unit.getAsString())) {
                        double candidate = number.getAsDouble();
                        if (Double.isFinite(candidate) && candidate >= signal.min && candidate <= signal.max) {
                            value = candidate; state = "available";
                        }
                    }
                }
            } else if (!item.isJsonNull()) state = "invalid";
            readings.add(new Reading(signal, value, state));
        }
        return new Frame(simulation, transport, source, null, timestamp, readings);
    }

    static Frame failure(boolean demo, String transport, String source, List<Signal> signals,
                         String message) {
        List<Reading> readings = new ArrayList<Reading>();
        for (Signal s : signals) readings.add(new Reading(s, null, "unavailable"));
        return new Frame(demo, transport, source, message, null, readings);
    }

    public static final class Source implements Closeable {
        private final boolean demo;
        private final Path file;
        private final URL url;
        private final List<Signal> signals;
        private final DiagnosticLog log;
        final String transport, label;

        Source(boolean demo, Path file, String endpoint, List<Signal> signals, DiagnosticLog log) throws Exception {
            this.demo = demo; this.file = file; this.signals = signals;
            this.log = log;
            this.url = endpoint == null ? null : new URL(endpoint);
            if (url != null && ((!url.getProtocol().equals("http") && !url.getProtocol().equals("https"))
                    || url.getUserInfo() != null || url.getHost().isEmpty()))
                throw new IllegalArgumentException("Endpoint HTTP(S) esplicito, senza credenziali nell'URL");
            transport = demo ? "demo" : file != null ? "file" : "http";
            label = demo ? "Campione dimostrativo" : file != null ? "File JSON importato"
                : "HTTP GET · " + url.getHost() + (url.getPort() == -1 ? "" : ":" + url.getPort());
        }

        public Frame read() throws IOException {
            HttpURLConnection connection = null;
            ReadTrace trace = new ReadTrace();
            Frame frame;
            try {
                if (demo) {
                    try (InputStream in = Telemetry.class.getResourceAsStream("/gte-demo.json")) {
                        if (in == null) throw new IOException("Campione demo assente");
                        trace.body = readLimited(in);
                    }
                } else if (file != null) {
                    try (InputStream in = Files.newInputStream(file)) { trace.body = readLimited(in); }
                }
                else {
                    // GET only, no redirects, cookies, credentials, discovery or writes.
                    connection = (HttpURLConnection) url.openConnection(Proxy.NO_PROXY);
                    connection.setRequestMethod("GET");
                    connection.setInstanceFollowRedirects(false);
                    connection.setConnectTimeout(1500);
                    connection.setReadTimeout(1500);
                    connection.setUseCaches(false);
                    connection.setRequestProperty("Accept", "application/json");
                    trace.stage = "connect";
                    int status = connection.getResponseCode();
                    trace.httpStatus = status;
                    trace.contentType = connection.getContentType();
                    trace.httpHeaders = connection.getHeaderFields();
                    long length = connection.getContentLengthLong();
                    trace.declaredLength = length >= 0 ? length : null;
                    trace.stage = "read";
                    try (InputStream in = status >= 400 ? connection.getErrorStream() : connection.getInputStream()) {
                        if (in != null) trace.body = readLimited(in);
                    }
                    if (trace.declaredLength != null && trace.body.length != trace.declaredLength)
                        throw new IOException("Corpo HTTP incompleto rispetto a Content-Length");
                    trace.complete = true;
                    if (status != 200) throw new IOException("HTTP " + status);
                }
                trace.complete = true;
                trace.stage = "parse";
                frame = parse(new String(trace.body, StandardCharsets.UTF_8), demo, transport, label, signals);
                trace.stage = "done";
            } catch (Exception e) {
                if (e instanceof CapturedReadException) {
                    trace.body = ((CapturedReadException) e).captured;
                    trace.truncated = ((CapturedReadException) e).truncated;
                }
                Throwable origin = e;
                while (origin.getCause() != null && origin.getCause() != origin) origin = origin.getCause();
                trace.errorType = origin.getClass().getName();
                trace.errorDetail = origin.getMessage();
                String reason = trace.httpStatus != null && trace.httpStatus != 200 ? "HTTP " + trace.httpStatus
                    : origin instanceof SocketTimeoutException ? "Timeout della sorgente"
                    : "Lettura fallita o snapshot non valido";
                frame = failure(demo, transport, label, signals, reason);
            } finally {
                if (connection != null) connection.disconnect();
            }
            trace.finishedAt = Instant.now();
            trace.elapsedMs = (System.nanoTime() - trace.startedNanos) / 1000000;
            // Log failures propagate: acquisition must not silently continue without recording.
            if (log != null) log.reading(frame, trace);
            return frame;
        }

        Frame loggingFailure() {
            return failure(demo, transport, label, signals, "Registrazione interrotta; acquisizione fermata");
        }

        @Override public void close() throws IOException { if (log != null) log.close(); }
    }

    static String asJson(Frame frame) {
        return JSON.toJson(frameJson(frame));
    }

    static JsonObject frameJson(Frame frame) {
        JsonObject result = new JsonObject();
        result.addProperty("greeting", "Ciao mondo");
        result.addProperty("simulation", frame.simulation);
        result.addProperty("transport", frame.transport);
        result.addProperty("source", frame.source);
        result.addProperty("freshness", frame.freshness(Instant.now()));
        result.addProperty("observed_at", frame.observedAt == null ? null : frame.observedAt.toString());
        result.addProperty("error", frame.error);
        JsonObject signals = new JsonObject();
        for (Reading reading : frame.readings) {
            JsonObject signal = new JsonObject();
            signal.addProperty("value", reading.value);
            signal.addProperty("unit", reading.signal.unit);
            signal.addProperty("state", reading.state);
            signals.add(reading.signal.id, signal);
        }
        result.add("signals", signals);
        return result;
    }
}

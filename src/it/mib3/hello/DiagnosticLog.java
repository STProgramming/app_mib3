package it.mib3.hello;

import com.google.gson.*;
import java.io.*;
import java.nio.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.security.*;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;

/** An append-only session journal of explicit inputs, not a MIB3-wide tap. */
public final class DiagnosticLog implements Closeable {
    static final long CHUNK_BYTES = 4L * 1024 * 1024;
    private static final long END_RESERVE = 2048;
    private static final Gson COMPACT = new GsonBuilder().serializeNulls().create();
    private final Path directory;
    private final String session = UUID.randomUUID().toString();
    private final String stem;
    private final long limit;
    private OutputStream output;
    private long total, chunkBytes, sequence;
    private int chunk;
    private boolean closed;

    DiagnosticLog(Path directory, long limit, String scope, List<Telemetry.Signal> signals) throws IOException {
        this.directory = directory.toAbsolutePath().normalize();
        this.limit = limit;
        Files.createDirectories(this.directory);
        this.stem = DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss.SSS'Z'")
            .withZone(ZoneOffset.UTC).format(Instant.now()) + "-" + session;
        rotate();
        JsonObject start = new JsonObject();
        start.addProperty("event", "session_start");
        start.addProperty("application", "Hello GTE / diagnostic logger 0.2");
        start.addProperty("capture_scope", scope);
        start.addProperty("runtime_java", System.getProperty("java.version"));
        start.addProperty("runtime_os", System.getProperty("os.name"));
        start.addProperty("runtime_arch", System.getProperty("os.arch"));
        start.addProperty("maximum_response_bytes", Telemetry.MAX_BYTES);
        start.addProperty("maximum_session_bytes", limit);
        start.addProperty("maximum_chunk_bytes", CHUNK_BYTES);
        start.add("signal_mapping", Telemetry.JSON.toJsonTree(signals));
        try { append(start); }
        catch (IOException e) { closeOutput(); closed = true; throw e; }
    }

    public Path firstFile() { return directory.resolve(stem + ".0001.jsonl"); }

    private void rotate() throws IOException {
        closeOutput();
        chunk++;
        Path path = directory.resolve(stem + String.format(Locale.ROOT, ".%04d.jsonl", chunk));
        output = Files.newOutputStream(path, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        chunkBytes = 0;
    }

    private void closeOutput() throws IOException {
        if (output != null) { output.close(); output = null; }
    }

    private byte[] encode(JsonObject event) {
        event.addProperty("log_schema_version", 1);
        event.addProperty("session_id", session);
        event.addProperty("sequence", ++sequence);
        event.addProperty("logged_at", Instant.now().toString());
        return (COMPACT.toJson(event) + "\n").getBytes(StandardCharsets.UTF_8);
    }

    private void write(byte[] record) throws IOException {
        if (chunkBytes > 0 && chunkBytes + record.length > CHUNK_BYTES) rotate();
        output.write(record);
        output.flush();
        chunkBytes += record.length;
        total += record.length;
    }

    private synchronized void append(JsonObject event) throws IOException {
        if (closed) throw new IOException("Il logger è già chiuso");
        byte[] record = encode(event);
        if (total + record.length + END_RESERVE > limit) {
            JsonObject stop = new JsonObject();
            stop.addProperty("event", "session_limit_reached");
            stop.addProperty("discarded_event", event.get("event").getAsString());
            stop.addProperty("discarded_record_bytes", record.length);
            stop.addProperty("capture_stopped", true);
            // The skipped record has not been written, so keep the sequence contiguous.
            sequence--;
            try { write(encode(stop)); }
            finally { closed = true; closeOutput(); }
            throw new IOException("Limite sessione log raggiunto; acquisizione interrotta");
        }
        try { write(record); }
        catch (IOException e) {
            closed = true;
            try { closeOutput(); } catch (IOException ignored) { }
            throw e;
        }
    }

    static JsonObject body(byte[] bytes, boolean complete, boolean truncated) {
        JsonObject body = new JsonObject();
        body.addProperty("bytes_captured", bytes.length);
        body.addProperty("complete", complete);
        body.addProperty("truncated", truncated);
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            StringBuilder hash = new StringBuilder();
            for (byte b : digest.digest(bytes)) hash.append(String.format(Locale.ROOT, "%02x", b & 255));
            body.addProperty("sha256", hash.toString());
        } catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
        try {
            CharsetDecoder decoder = StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT);
            body.addProperty("encoding", "utf-8");
            body.addProperty("content", decoder.decode(ByteBuffer.wrap(bytes)).toString());
        } catch (CharacterCodingException e) {
            body.addProperty("encoding", "base64");
            body.addProperty("content", Base64.getEncoder().encodeToString(bytes));
        }
        return body;
    }

    synchronized void reading(Telemetry.Frame frame, Telemetry.ReadTrace trace) throws IOException {
        JsonObject event = new JsonObject();
        event.addProperty("event", "source_read");
        event.addProperty("started_at", trace.startedAt.toString());
        event.addProperty("finished_at", trace.finishedAt.toString());
        event.addProperty("elapsed_ms", trace.elapsedMs);
        event.addProperty("transport", frame.transport);
        event.addProperty("source", frame.source);
        event.addProperty("stage", trace.stage);
        event.addProperty("http_status", trace.httpStatus);
        event.addProperty("content_type", trace.contentType);
        event.addProperty("declared_content_length", trace.declaredLength);
        event.add("http_response_headers", Telemetry.JSON.toJsonTree(trace.httpHeaders));
        event.addProperty("error_type", trace.errorType);
        event.addProperty("error_detail", trace.errorDetail);
        event.add("response", body(trace.body, trace.complete, trace.truncated));
        event.add("interpreted", Telemetry.frameJson(frame));
        append(event);
    }

    synchronized void stream(byte[] bytes) throws IOException {
        JsonObject event = new JsonObject();
        event.addProperty("event", "stream_chunk");
        event.add("response", body(bytes, true, false));
        append(event);
    }

    synchronized void streamEof(long bytes) throws IOException {
        JsonObject event = new JsonObject();
        event.addProperty("event", "stream_eof");
        event.addProperty("bytes_captured", bytes);
        append(event);
    }

    @Override public synchronized void close() throws IOException {
        if (closed) return;
        JsonObject end = new JsonObject();
        end.addProperty("event", "session_end");
        end.addProperty("bytes_before_end", total);
        try { write(encode(end)); }
        finally { closed = true; closeOutput(); }
    }
}

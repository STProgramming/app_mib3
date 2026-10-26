"""Summarize Hello GTE JSONL sessions; optionally recover original response bytes."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import uuid


def response_bytes(response: dict) -> bytes:
    if response["encoding"] == "utf-8":
        content = response["content"].encode("utf-8")
    elif response["encoding"] == "base64":
        content = base64.b64decode(response["content"], validate=True)
    else:
        raise ValueError("Codifica del contenuto sconosciuta")
    if len(content) != response["bytes_captured"]:
        raise ValueError("Lunghezza contenuto incoerente")
    if hashlib.sha256(content).hexdigest() != response["sha256"]:
        raise ValueError("SHA-256 del contenuto non valido")
    return content


def field_paths(value, prefix="", depth=0):
    if depth >= 64:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            path = prefix + "/" + key.replace("~", "~0").replace("/", "~1")
            yield path
            yield from field_paths(child, path, depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from field_paths(child, prefix + "/" + str(index), depth + 1)


def summarize(path: Path, *, extract: Path | None = None, fields: bool = False) -> dict:
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    if not files:
        raise ValueError("Nessun file JSONL trovato")
    events, statuses = Counter(), Counter()
    sessions, keys, previous, streams = set(), set(), {}, {}
    ended, stream_sessions, stream_ended = set(), set(), set()
    total_bytes = partial = errors = gaps = 0
    with ExitStack() as stack:
        for file in files:
            with file.open(encoding="utf-8") as source:
                for number, line in enumerate(source, 1):
                    try:
                        record = json.loads(line)
                        if record["log_schema_version"] != 1:
                            raise ValueError("Versione log non supportata")
                        session = str(uuid.UUID(record["session_id"]))
                        sequence = record["sequence"]
                        if type(sequence) is not int or sequence <= previous.get(session, 0):
                            raise ValueError("Sequenza sessione non crescente")
                        gaps += sequence - previous.get(session, 0) - 1
                        previous[session] = sequence
                        sessions.add(session)
                        event = record["event"]
                        events[event] += 1
                        if event in {"session_end", "session_limit_reached"}:
                            ended.add(session)
                        if event == "session_start" and record.get("capture_scope") == "stdin_bytes":
                            stream_sessions.add(session)
                        if event == "stream_eof":
                            stream_ended.add(session)
                        response = record.get("response")
                        if response is None:
                            continue
                        content = response_bytes(response)
                        total_bytes += len(content)
                        partial += int(not response["complete"] or response["truncated"])
                        if record.get("http_status") is not None:
                            statuses[str(record["http_status"])] += 1
                        errors += int(record.get("error_type") is not None)
                        if fields and event == "source_read":
                            try:
                                decoded = json.loads(content)
                                keys.update(field_paths(decoded))
                            except (UnicodeError, ValueError, RecursionError):
                                pass
                        if extract is not None:
                            root = extract.resolve()
                            destination = root / session
                            assert destination.is_relative_to(root)
                            destination.mkdir(parents=True, exist_ok=True)
                            if event == "stream_chunk":
                                if session not in streams:
                                    streams[session] = stack.enter_context((destination / "stream.bin").open("xb"))
                                streams[session].write(content)
                            elif event == "source_read":
                                with (destination / f"response-{sequence:06d}.bin").open("xb") as output:
                                    output.write(content)
                    except Exception as error:
                        raise ValueError(f"{file.name}:{number}: {error}") from error
    result = {
        "files": len(files), "sessions": len(sessions), "events": dict(events),
        "http_statuses": dict(statuses), "bytes_captured": total_bytes,
        "partial_responses": partial, "read_errors": errors, "missing_sequences": gaps,
        "unclosed_sessions": len(sessions - ended),
        "streams_without_eof": len(stream_sessions - stream_ended),
    }
    if fields:
        result["observed_json_paths"] = sorted(keys)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="File JSONL o cartella della sessione")
    parser.add_argument("--fields", action="store_true", help="Elenca i percorsi JSON, anche sconosciuti all'app")
    parser.add_argument("--extract", type=Path, help="Recupera i byte in una cartella nuova, senza sovrascrivere file")
    arguments = parser.parse_args()
    try:
        print(json.dumps(summarize(arguments.path, extract=arguments.extract, fields=arguments.fields),
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(f"Errore lettura log: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/bin/sh
# Desktop/lab preview. This script is not a vehicle installer.
set -eu
task_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_jar="$task_dir/hello-gte.jar"
if [ ! -f "$task_jar" ]; then task_jar="$task_dir/dist/hello-gte/hello-gte.jar"; fi
if [ ! -f "$task_jar" ]; then printf '%s\n' 'Eseguire prima: python3 tools/build.py' >&2; exit 2; fi
task_java=java
if [ -n "${JAVA_HOME:-}" ]; then task_java="$JAVA_HOME/bin/java"; fi
exec "$task_java" -jar "$task_jar" --demo --window --log-dir "$task_dir/logs"

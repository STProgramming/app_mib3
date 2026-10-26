#!/bin/sh
# One-shot probe. Needs an existing shell/validated launcher; it is not an installer.
set -eu
LC_ALL=C
export LC_ALL
umask 077

usage() {
    printf '%s\n' \
        'Uso: sh mib3-hello.sh --output-dir /percorso/usb [--lab]' \
        'Crea hello.txt una sola volta. Non avvia servizi e non installa nulla.' \
        '--lab marca SEMPRE il risultato come prova di laboratorio.'
}

fail() {
    printf 'Errore: %s\n' "$1" >&2
    exit 1
}

output_dir=
lab=no
while [ "$#" -gt 0 ]; do
    case "$1" in
        --output-dir)
            [ "$#" -ge 2 ] || fail 'Manca il percorso dopo --output-dir.'
            [ -z "$output_dir" ] || fail '--output-dir ripetuto.'
            output_dir=$2
            shift 2
            ;;
        --lab) lab=yes; shift ;;
        --help|-h) usage; exit 0 ;;
        *) fail 'Argomento sconosciuto. Usare --help.' ;;
    esac
done

[ -n "$output_dir" ] || fail 'Specificare --output-dir con una directory esistente.'
case "$output_dir" in
    /*) ;;
    *) fail 'Il percorso di output deve essere assoluto, come visto dalla shell.' ;;
esac
[ -d "$output_dir" ] || fail 'La directory di output non esiste.'
# Resolve the chosen directory, without creating directories or guessing USB ports.
output_dir=$(CDPATH= cd -P "$output_dir" && pwd -P) || fail 'Directory non accessibile.'
report=$output_dir/hello.txt
[ ! -e "$report" ] && [ ! -L "$report" ] || fail 'hello.txt esiste gia: non lo sovrascrivo.'

kernel=$(uname -s 2>/dev/null) || kernel=unavailable
arch=$(uname -m 2>/dev/null) || arch=unavailable
if [ "$lab" = yes ]; then
    context=LAB_NOT_VEHICLE_VERIFICATION
else
    [ "$kernel" = Linux ] || fail 'Sistema non Linux. Per una prova PC usare --lab.'
    [ -d /lge/app_ro ] && [ -d /vw ] || fail 'Struttura MOI3 LG non riconosciuta. Nessun file creato.'
    case "$arch" in
        aarch64|arm64) ;;
        *) fail 'Architettura ARM64 non riconosciuta. Nessun file creato.' ;;
    esac
    context=MOI3_LG_CANDIDATE_UNVERIFIED
fi

report_started=no
trap 'status=$?; if [ "$status" -ne 0 ] && [ "$report_started" = yes ]; then printf "%s\n" "Report incompleto: manca report_complete=yes." >&2; fi' 0
trap 'exit 130' INT
trap 'exit 143' TERM
# Noclobber also protects a file created between the existence check and open.
set -C
exec 3> "$report"
report_started=yes

section() {
    printf '\n[%s]\n' "$1" >&3
}

read_file() {
    printf 'path=%s\n' "$1" >&3
    if [ -f "$1" ] && [ -r "$1" ] && command -v head >/dev/null 2>&1; then
        # Bound each read. Do not source os-release or execute any file read here.
        head -c "$2" "$1" >&3 2>/dev/null || printf '\nread_status=failed\n' >&3
        printf '\n' >&3
    else
        printf 'read_status=unavailable\n' >&3
    fi
}

printf '%s\n' 'Ciao mondo' 'probe_version=1' "context=$context" \
    'firmware_1989_compatibility=not_verified' \
    'vehicle_signals=not_collected' 'launcher=external_not_supplied' >&3
utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null) || utc=unavailable
printf 'device_clock_utc=%s\npid=%s\noutput_directory=%s\n' "$utc" "$$" "$output_dir" >&3

section system
printf 'kernel=%s\narchitecture=%s\n' "$kernel" "$arch" >&3
release=$(uname -r 2>/dev/null) || release=unavailable
uid=$(id -u 2>/dev/null) || uid=unavailable
gid=$(id -g 2>/dev/null) || gid=unavailable
printf 'kernel_release=%s\nuid=%s\ngid=%s\n' "$release" "$uid" "$gid" >&3
read_file /etc/os-release 4096
read_file /proc/uptime 128
read_file /proc/meminfo 4096

section known_paths_presence_only
for path in /lge/app_ro/hmi /lge/app_rw /lge/webengine /vw /usr/bin/java /usr/bin/rsi-send /usr/bin/rsi-subscribe; do
    if [ -e "$path" ]; then
        printf '%s=present\n' "$path" >&3
    else
        printf '%s=absent\n' "$path" >&3
    fi
done

section board_fields_if_available
# Explicit allowlist: do not read fazit, secure_id, keys or vehicle identifiers.
for field in hwpn vwagpn board_id platform_id variant_id grade_id brand_id market_id; do
    read_file "/sys/devices/soc/soc:common_gpio_default/$field" 256
done

printf '\nreport_complete=yes\n' >&3
exec 3>&-
printf 'Creato: %s\nContesto: %s\n' "$report" "$context"

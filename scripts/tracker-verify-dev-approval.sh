#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Fixed trusted location. No environment override is permitted.
ROOT=/etc/tracker-release
KEY="$ROOT/dev-signing-public.pem"

[[ $# -eq 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || {
    echo "DENIED: Invalid commit identifier" >&2
    exit 1
}

TARGET="$1"
APPROVAL="$ROOT/approvals/$TARGET.approval"
SIGNATURE="$ROOT/approvals/$TARGET.sig"

for FILE in "$ROOT" "$ROOT/approvals" \
            "$KEY" "$APPROVAL" "$SIGNATURE"; do

    [[ -e "$FILE" && ! -L "$FILE" ]] || {
        echo "DENIED: Missing or unsafe approval material" >&2
        exit 1
    }

    [[ "$(stat -c %u "$FILE")" == 0 ]] || {
        echo "DENIED: Approval material is not root-owned" >&2
        exit 1
    }

    MODE="$(stat -c %a "$FILE")"
    (( (8#$MODE & 0022) == 0 )) || {
        echo "DENIED: Writable approval material" >&2
        exit 1
    }
done

[[ -d "$ROOT" && -d "$ROOT/approvals" ]] || exit 1
[[ -f "$KEY" && -f "$APPROVAL" && -f "$SIGNATURE" ]] || exit 1

EXPECTED=$(mktemp)
trap 'rm -f "$EXPECTED"' EXIT

printf 'tracker-dev-qualified-v1\ncommit=%s\n' \
    "$TARGET" > "$EXPECTED"

cmp -s "$EXPECTED" "$APPROVAL" || {
    echo "DENIED: Approval is for a different commit" >&2
    exit 1
}

openssl pkeyutl -verify \
    -pubin \
    -inkey "$KEY" \
    -rawin \
    -in "$APPROVAL" \
    -sigfile "$SIGNATURE" \
    >/dev/null 2>&1 || {
        echo "DENIED: Invalid DEV approval signature" >&2
        exit 1
    }

echo "DEV_APPROVAL_VERIFIED=$TARGET"

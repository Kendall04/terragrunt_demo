#!/bin/sh
# Closed image entrypoint. No network, credentials, root, or system-store writes.
set -eu
umask 077
refuse() { printf '%s\n' "$1" >&2; exit 78; }
case "${1:-}" in
  readiness-probe) exec dotnet /app/terragrunt-demo.dll "$@" ;;
  '') test "$#" = 0 || refuse SQL_TRUST_COMMAND_REFUSED ;;
  database-migrate) test "$#" = 2 && test "$2" = --confirm-schema-change || refuse SQL_TRUST_COMMAND_REFUSED ;;
  *) refuse SQL_TRUST_COMMAND_REFUSED ;;
esac
test "$(id -u)" = 1654 || refuse SQL_TRUST_USER_REFUSED
test "${Database__SecurityProfile:-}" = validated-v2 || refuse DATABASE_VALIDATED_PROFILE_REQUIRED
case "${APP_ENV:-}" in dev|prod) ;; *) refuse SQL_TRUST_ENVIRONMENT_REQUIRED ;; esac
manifest_b64=${SQL_TRUST_MANIFEST_B64:-}
test -n "$manifest_b64" && test "${#manifest_b64}" -le 40000 || refuse SQL_TRUST_MANIFEST_REQUIRED
test -n "${SQL_TRUST_MANIFEST_SHA256:-}" || refuse SQL_TRUST_MANIFEST_REQUIRED
dir=$(mktemp -d /tmp/sql-trust.XXXXXXXX)
trap 'rm -rf -- "$dir"' EXIT
printf '%s' "${SQL_TRUST_MANIFEST_B64:-}" | base64 -d > "$dir/manifest.json" 2>/dev/null || refuse SQL_TRUST_ENCODING_REFUSED
actual=$(sha256sum "$dir/manifest.json" | cut -d ' ' -f 1)
test "$actual" = "$SQL_TRUST_MANIFEST_SHA256" || refuse SQL_TRUST_MANIFEST_HASH_REFUSED
# Reject multiple JSON documents, repeated keys and all unrecognized fields.
jq --stream -s -e 'map(if length == 2 then .[0] else .[0][0:-1] end) | group_by(.) | all(length == 1)' "$dir/manifest.json" >/dev/null 2>&1 || refuse SQL_TRUST_SCHEMA_REFUSED
jq -s -e --arg env "$APP_ENV" --arg host "${Database__ExpectedCertificateHostName:-}" '
  length == 1 and (.[0] |
    (keys == ["anchors","environment","hostname","schema","version"] or keys == ["anchors","environment","hostname","schema","transition","version"]) and
    .schema == "SQL_TLS_TRUST_V1" and .environment == $env and .hostname == $host and
    (.version | type == "string" and test("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")) and
    (.anchors | type == "array" and length >= 1 and length <= 3 and
      all(.[]; keys == ["der_base64","kind","sha256"] and
        (.kind == "ca" or .kind == "dev-leaf-transition") and
        (.sha256 | type == "string" and test("^[a-f0-9]{64}$")) and
        (.der_base64 | type == "string" and length <= 8192 and test("^[A-Za-z0-9+/]+={0,2}$"))) and
      (map(.sha256) | unique | length) == length) and
    ([.anchors[] | select(.kind == "ca")] | length >= 1) and
    ([.anchors[] | select(.kind == "dev-leaf-transition")] | length <= 1) and
    (if any(.anchors[]; .kind == "dev-leaf-transition") then
      $env == "dev" and .hostname == "sql.demo.internal" and
      (.transition | keys == ["not_after","not_before"] and
        all(.[]; type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")))
    else has("transition") | not end))' "$dir/manifest.json" >/dev/null 2>&1 || refuse SQL_TRUST_SCHEMA_REFUSED
unset SQL_TRUST_TRANSITION_UNTIL
if jq -e 'has("transition")' "$dir/manifest.json" >/dev/null; then
  start=$(date -u -d "$(jq -r .transition.not_before "$dir/manifest.json")" +%s) || refuse SQL_TRUST_TRANSITION_REFUSED
  end=$(date -u -d "$(jq -r .transition.not_after "$dir/manifest.json")" +%s) || refuse SQL_TRUST_TRANSITION_REFUSED
  now=$(date -u +%s)
  cap=$(date -u -d 2026-12-04T20:09:56Z +%s)
  test "$start" -le "$now" && test "$now" -lt "$end" && test "$end" -le "$cap" && test $((end-start)) -le 604800 || refuse SQL_TRUST_TRANSITION_REFUSED
  SQL_TRUST_TRANSITION_UNTIL=$(jq -r .transition.not_after "$dir/manifest.json")
  export SQL_TRUST_TRANSITION_UNTIL
fi
cat /etc/ssl/certs/ca-certificates.crt > "$dir/bundle.pem"
count=$(jq '.anchors | length' "$dir/manifest.json")
i=0
while [ "$i" -lt "$count" ]; do
  jq -r --argjson i "$i" '.anchors[$i].der_base64' "$dir/manifest.json" | base64 -d > "$dir/anchor.der" || refuse SQL_TRUST_CERTIFICATE_REFUSED
  actual=$(sha256sum "$dir/anchor.der" | cut -d ' ' -f 1)
  expected=$(jq -r --argjson i "$i" '.anchors[$i].sha256' "$dir/manifest.json")
  test "$actual" = "$expected" || refuse SQL_TRUST_ANCHOR_HASH_REFUSED
  openssl x509 -inform DER -in "$dir/anchor.der" -outform DER -out "$dir/roundtrip.der" 2>/dev/null || refuse SQL_TRUST_CERTIFICATE_REFUSED
  cmp -s "$dir/anchor.der" "$dir/roundtrip.der" || refuse SQL_TRUST_CERTIFICATE_REFUSED
  openssl x509 -inform DER -in "$dir/anchor.der" -out "$dir/anchor.pem"
  # Inspect only the requested X.509 extensions. Subject/issuer strings are
  # attacker controlled and must never satisfy CA or key-usage assertions.
  openssl x509 -in "$dir/anchor.pem" -noout -ext basicConstraints > "$dir/constraints.txt"
  openssl x509 -in "$dir/anchor.pem" -noout -ext keyUsage > "$dir/key-usage.txt"
  kind=$(jq -r --argjson i "$i" '.anchors[$i].kind' "$dir/manifest.json")
  if [ "$kind" = ca ]; then
    grep -Eq '^[[:space:]]*CA:TRUE(, pathlen:[0-9]+)?[[:space:]]*$' "$dir/constraints.txt" || refuse SQL_TRUST_CA_REQUIRED
    grep -Eq '(^|,[[:space:]]*|^[[:space:]]*)Certificate Sign(,|[[:space:]]*$)' "$dir/key-usage.txt" || refuse SQL_TRUST_CA_REQUIRED
    subject=$(openssl x509 -in "$dir/anchor.pem" -noout -subject -nameopt RFC2253 | cut -d= -f2-)
    issuer=$(openssl x509 -in "$dir/anchor.pem" -noout -issuer -nameopt RFC2253 | cut -d= -f2-)
    test "$subject" = "$issuer" || refuse SQL_TRUST_ROOT_REQUIRED
    openssl verify -CAfile "$dir/anchor.pem" -no-CApath -no-CAstore -check_ss_sig "$dir/anchor.pem" >/dev/null 2>&1 || refuse SQL_TRUST_CERTIFICATE_REFUSED
  else
    test "$actual" = 206095fa0ba9e17a84c80eff5021db93d05e2dc377e982a64d517696ed21a1e7 || refuse SQL_TRUST_LEAF_PIN_REFUSED
    grep -Eq '^[[:space:]]*CA:FALSE[[:space:]]*$' "$dir/constraints.txt" || refuse SQL_TRUST_LEAF_PIN_REFUSED
    openssl verify -CAfile "$dir/anchor.pem" -no-CApath -no-CAstore -check_ss_sig -purpose sslserver -verify_hostname sql.demo.internal "$dir/anchor.pem" >/dev/null 2>&1 || refuse SQL_TRUST_CERTIFICATE_REFUSED
  fi
  cat "$dir/anchor.pem" >> "$dir/bundle.pem"
  i=$((i+1))
done
chmod 400 "$dir/bundle.pem"
mkdir "$dir/home"
export HOME="$dir/home" SSL_CERT_FILE="$dir/bundle.pem" SSL_CERT_DIR=/app/empty-cert-dir
SQL_TRUST_BUNDLE_SHA256=$(sha256sum "$dir/bundle.pem" | cut -d ' ' -f 1)
export SQL_TRUST_BUNDLE_SHA256
printf 'SQL_TRUST_PREPARED environment=%s manifest_sha256=%s bundle_sha256=%s\n' "$APP_ENV" "$SQL_TRUST_MANIFEST_SHA256" "$SQL_TRUST_BUNDLE_SHA256"
# The fresh API process inherits trust before .NET/OpenSSL loads any roots.
trap - EXIT
exec dotnet /app/terragrunt-demo.dll "$@"

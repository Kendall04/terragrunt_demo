# Opt-in SQL laboratory trust - qualified locally on Linux, not deployed

One self-signed **server leaf**, CA=false, RSA2048/SHA256, SAN `sql.demo.internal`.
Public DER SHA256: `6a45fbcadf8a0a44ffed3f9b78de396b872af430c856b3cb041a29c2ece87738`.
Valid `2026-10-27T03:21:58.0000000+00:00` through `2026-11-26T03:21:58.0000000+00:00` (30 days).
The private key is outside this repository/build context under a private local ACL.
Only the public `.crt` and non-secret metadata are checked in. No CA/PKI was created.

## Explicit build recipe

The normal `demo-api/Dockerfile` is byte-for-byte unchanged. The opt-in file is
`deploy/sql-lab/Dockerfile`, selected from the same `demo-api` build context with
`-f deploy/sql-lab/Dockerfile`. This variant has now been built and run in the owner-authorized laptop WSL.
See `native-linux-image.json`. Only the image truststore was changed; no Windows/
WSL host trust, SQL installation, remote publication or AWS operation occurred.

The recipe is exactly the pinned normal build plus one public trust insertion:
copy the one reviewed `.crt`, match its DER fingerprint, verify it with OpenSSL
for sslserver/current validity/name, then update the image truststore. There is
no package installation, network download, private-key COPY or mutable base.
The image returns to UID1654; root is used only for the image-build trust update.
Do not weaken or omit the build verification to use an expired/wrong certificate.
Normal builds do not acquire this trust; no CI/delivery caller was activated.

Application and migration configuration retain `Encrypt=True`,
`TrustServerCertificate=False`, and `HostNameInCertificate=sql.demo.internal` in
the validated-v2 profile. The migration command is a separate process in the
same intended image/trust model, not a privileged credential in the runtime task.
No ServerCertificate pin file or TLS validation callback is introduced.
Connecting to the reviewed private IP while validating that name avoids a DNS
record for this override; native SQL/SqlClient E2E remains unproven.

## Scope and next gate

Owner approval covers local generation and preparation of public image trust.
It does not install the private key/certificate on SQL, change OS permissions,
upload AWS material, install Windows trust, create IAM, authorize deployment or
resolve previous SSM/retirement restrictions. No such operation occurred here.
The leaf private key must never enter a build context, image, Git or review archive.
`.dockerignore` blocks key/PEM/PFX/P12/PKCS8, AWS/SSH/Git metadata and other CRT files;
the public leaf has the sole explicit CRT exception. Root Git rules already ignore
private-key formats. The private material is outside both source and task evidence.

The .NET tests use only the public certificate and an in-memory CustomRootTrust;
they do not import a certificate store. Chain tests use the recorded valid period
for repeatability, with explicit untrusted/expired/name negatives. The lab image
build verifies current validity; tests of an archived leaf do not extend its life.
Linux system trust, name and expiry checks now PASS against the actual image.
SQL TLS handshake, private-key installation/distribution and current protected
deployment admission remain separate gates. No automated
renewal exists; do not silently regenerate or substitute material after expiry.

The owner explicitly authorized laptop WSL after the earlier VM-only limitation.
Existing Ubuntu24.04 WSL/Docker were used with2CPU/4GiB and no active containers at
preflight. No external bastion, new VM, credentials or private-key transfer was used.
The context contained32 tracked Git blobs/76020 source bytes; it was verified before
build and remained outside all private material. Initial cold-cache/offline restore
and transient-/tmp failures are preserved, not hidden or turned into successful runs.

Native OpenSSL checks used the installed system truststore without a custom CAfile
for the positive case. Wrong name, explicitly absent trust and post-expiry time were
rejected. The API smoke ran as UID1654 with read-only root, network=none, no published
ports and dropped capabilities: liveness200, readiness503 without SQL/KMS. That smoke
explicitly used legacy-v1/migrations-off, so it is not strict SQL-profile acceptance.
The disposable API container was stopped normally and removed. The qualified local
image is retained for reuse; no image archive, registry push or Docker prune occurred.
The old recovery tar is still historical and was not rebuilt by this qualification.

Sources: [Microsoft SQL Linux encrypted connections](https://learn.microsoft.com/en-us/sql/linux/security/encrypted-connections?view=sql-server-ver16)
and [SqlClient certificate validation](https://learn.microsoft.com/en-us/sql/connect/ado-net/encryption-and-certificate-validation?view=sql-server-ver16).

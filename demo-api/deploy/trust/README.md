# Opt-in SQL laboratory trust - prepared locally, not deployed

One self-signed **server leaf**, CA=false, RSA2048/SHA256, SAN `sql.demo.internal`.
Public DER SHA256: `6a45fbcadf8a0a44ffed3f9b78de396b872af430c856b3cb041a29c2ece87738`.
Valid `2026-10-27T03:21:58.0000000+00:00` through `2026-11-26T03:21:58.0000000+00:00` (30 days).
The private key is outside this repository/build context under a private local ACL.
Only the public `.crt` and non-secret metadata are checked in. No CA/PKI was created.

## Explicit build recipe

The normal `demo-api/Dockerfile` is byte-for-byte unchanged. The opt-in file is
`deploy/sql-lab/Dockerfile`, selected from the same `demo-api` build context with
`-f deploy/sql-lab/Dockerfile`. This is a future build instruction, not a claim
that this increment ran Docker, installed trust or published an image.

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
Actual Linux image trust, SQL TLS handshake, private-key installation/distribution
and current protected deployment admission remain separate gates. No automated
renewal exists; do not silently regenerate or substitute material after expiry.

No verified local VM SSH destination/mount is available in this thread. Minimum
missing environment metadata: the authorized local VM address/alias, SSH user and
host-key binding, plus the mounted Linux workspace path. No password/key in chat
is needed. External bastions and WSL were not used as substitutes.

Sources: [Microsoft SQL Linux encrypted connections](https://learn.microsoft.com/en-us/sql/linux/security/encrypted-connections?view=sql-server-ver16)
and [SqlClient certificate validation](https://learn.microsoft.com/en-us/sql/connect/ado-net/encryption-and-certificate-validation?view=sql-server-ver16).

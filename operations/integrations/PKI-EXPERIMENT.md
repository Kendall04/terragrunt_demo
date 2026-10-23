# PKI experiment — NOT ACCEPTED; ECS runtime integration PAUSED

Owner architectural clarification, 2026-10-23: ECS contains **one application**.
Blue/green are deployment slots of that same API, not two microservices. The
implemented API calls SQL Server via EF/SQLClient and AWS KMS via its SDK. There
is no internal business HTTP service-to-service call requiring this mTLS adapter.
The backup CLI, periodic observer and local Sentinel libraries are not deployed
business microservices. See [architecture](../../terraform/docs/architecture.md#current-contract--topology-and-networking)
and [API composition](../../demo-api/terragrunt-demo/Program.cs).

`Ecs.Identity` and `Ecs.Identity.LocalProbe` are preserved experimental source,
not part of the existing API solution, startup, task definition, deployment or
architecture. Their text-api/recovery-observer identities are test fixtures; no
second application/service was created in ECS. Do not wire or deploy them merely
to justify PKI. The roadmap requirement remains subject to a genuine consumer
boundary and an explicit architectural scope decision.

## Provenance and measured result

The actual upstream revision is pinned in upstream-sources.json. Three public
net8.0 modules were built and packed locally without source edits or network
restore, using SDK 9.0.101/reference packs already installed. The net10.0 consumer
built with installed SDK 10.0.402, zero warnings/errors. PackageReference follows
the real upstream package-consumer pattern; local package hashes are preserved in
[pki-local-packages.json](pki-local-packages.json) and the two consumer lock files.
No package was pushed or published; package-byte reproducibility is not claimed.

The last complete native Windows characterization (07) had **21/22 checks pass**:
mutual calls, authorization/header rejection, foreign CA/identity/DNS rejection,
actual server fingerprint observation, new server/client generation observations,
CAS conflict/invalid replacement refusal and retired client lease refusal. It
was **FAILED overall** because the same-process unspecified-client call got HTTP
200. This receipt is not a full PKI qualification and predates the child probe.

Characterization 08 observed different new TCP connections (client port equals
server-observed remote port, different Kestrel connection IDs). For the HTTP200
unspecified-client request, Kestrel's actual Connection.ClientCertificate SHA256
matched both the authenticated claim and the fixture's text-api credential. This
was not demonstrated anonymous access, nor reuse of an HTTP connection. Native
credential selection/cache remains the likely explanation; no precise internal
Schannel mechanism was proven. Client-side LocalCertificate/IsMutuallyAuthenticated
alone were insufficient diagnostics in this Windows run.

The independent --anonymous-no-key client receives only the public root and
loopback port, never creates a CA/client key, and uses explicit null client
selection. It exited without a JSON receipt in 08; the parent then failed parsing
empty stdout. The child failure cause is unresolved. It is **not** a successful
no-certificate rejection test. No subsequent run is authorized by this document.
PKI runtime work is paused by the owner scope clarification.

## Preservation and cleanup

Original native01–08 logs and native08 source snapshot remain in the worker's
pki-qualification evidence directory; failed receipts were not replaced by PASS.
Normal shutdown disposed both own Kestrel hosts in the measured runs. Native08
reported zero remaining key files owned by the upstream TLS import helper.
That metric covers this process's tracked imports, not unrelated user keys.
Test root/intermediate keys lived in memory; there was no CA/trust-store install,
Norton change, foreign-store cleanup, force-PID termination or AWS action.

The real application/database/KMS contract is unchanged. Keep experimental
compatibility distinct from an accepted integration or a deployed microservice.

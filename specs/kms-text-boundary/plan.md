# Technical plan — KMS text boundary

[spec.md](spec.md) remains the source of truth and review contract. This plan selects implementation details only. Verdict: `READY_FOR_IMPLEMENTATION`.

## Evidence and boundary

- `demo-api/terragrunt-demo/Controllers/DemoTextController.cs`: POST binds `InsertTextRequest.Text`, rejects blank text, sends `InsertTextCommand` through MediatR, and returns HTTP 200 with `DemoTextDto`.
- `Features/Texts/Commands/InsertTextCommandHandler.cs`: awaits `IEncryptionService.EncryptAsync`, then creates `DemoText` and calls `IDemoTextRepository.AddAsync`; returns the original plaintext DTO. `Repositories/ITextRepository.cs` persists through EF `SaveChangesAsync`.
- `Services/IEncryptionService.cs` also contains `KmsEncryptionService`. It supplies exactly `Encoding.UTF8.GetBytes(plainText)` in a `MemoryStream` to `EncryptRequest.Plaintext`, with `KeyId` from `KMS_KEY_ID` and no explicit algorithm. There is no BOM, normalization, trimming, or application-level plaintext base64 conversion. Measure these bytes, not UTF-16 string length, JSON body length, or transport base64 length. Ciphertext is base64-encoded for persistence. GET uses `GetAllTextsQueryHandler` and the inverse base64/KMS/UTF-8 path.
- **MAX = 4096 plaintext bytes, inclusive.** The authoritative [AWS KMS Encrypt API contract](https://docs.aws.amazon.com/kms/latest/APIReference/API_Encrypt.html) specifies 4096 bytes for symmetric `SYMMETRIC_DEFAULT` and identifies it as the default algorithm when omitted (consulted during planning). The wrapper uses that default; `terraform/infra/shared/modules/kms_key/key.tf` declares an `ENCRYPT_DECRYPT` key, documents symmetric use, and does not select an asymmetric key spec. This is repository-contract evidence, not verification of a deployed key.
- Explicit API validation uses `BadRequest(string)` (HTTP 400), including pagination errors and the existing `Text cannot be empty.1234` message. `[ApiController]` also handles binding/model errors; there is no custom global exception translator or validation pipeline in `Program.cs`.
- KDD: `terraform/docs/architecture.md` application/data section and `decisions-and-limitations.md` B10 identify this gap; backend guidance requires ciphertext persistence. Larger-payload architecture is not selected. Read `terraform/docs/validation.md` before executing checks.

## Implementation shape and expected paths

Paths below are repository-relative.

1. Modify `demo-api/terragrunt-demo/Services/IEncryptionService.cs`: keep one named 4096-byte constant in the KMS implementation with the technical-source comment. Use `Encoding.UTF8.GetByteCount` before allocating the request stream; if greater than MAX, throw a dedicated local `PlaintextTooLargeException`. Encode accepted input using the existing `Encoding.UTF8.GetBytes` behavior. Keep key, algorithm, cancellation propagation, ciphertext conversion, and decryption unchanged.
2. Add `demo-api/terragrunt-demo/Services/PlaintextTooLargeException.cs`: carry the maximum byte count, without plaintext or AWS details. The encryption adapter owns this restriction because it owns the encoding and direct-KMS mechanism; controller-only validation could be bypassed by handler/service callers. Do not duplicate the size policy in the controller or handler.
3. Modify `demo-api/terragrunt-demo/Controllers/DemoTextController.cs`: catch only that exception around POST's mediator call and return `BadRequest` with `Text must not exceed 4096 UTF-8 bytes.` (derive the number from the exception). Preserve blank-input validation precedence and its exact existing message. Do not translate unrelated AWS, cancellation, or persistence exceptions into validation failures. No new error envelope, 413 response, middleware, or validation dependency is needed.
4. Add `demo-api/terragrunt-demo.Tests/KmsEncryptionServiceTests.cs` and `TextEndpointTests.cs`; extend `TextHandlersTests.cs` if needed for shared flow assertions. No production handler/repository/DI changes are expected.
5. During implementation, narrowly update the application/data boundary statement in `terraform/docs/architecture.md` and test coverage in `terraform/docs/validation.md` after behavior is verified, per repository guidance. Do not rewrite the spec or unrelated backlog. This planning task creates only this plan.

## Deterministic validation and acceptance mapping

Use existing xUnit and `WebApplicationFactory<Program>` dependencies. Existing handler tests have private in-memory repository and prefix-encryption doubles; those prove flow but cannot prove actual KMS encoding. Add a recording SDK double via the `IAmazonKeyManagementService` seam (for example, an SDK-client subclass overriding `EncryptAsync`, with explicit dummy credentials/region and no base/network call). Capture stream bytes during the call and return synthetic ciphertext. No mocking package is necessary.

For endpoint tests, follow the existing health factory pattern: disable startup migrations, replace the repository and KMS registrations, configure a dummy key, and use the real encryption service and MediatR handler. Replace dependency health checks if exercised; never resolve a real AWS client or SQL repository for these requests. Keep fake state isolated per test.

| Spec AC | Implementation and evidence |
| --- | --- |
| 1 | Service guard; rejected service and POST cases assert zero SDK Encrypt calls and zero repository writes. |
| 2 | Capture accepted request bytes and compare to `Encoding.UTF8.GetBytes(input)`; guard uses the same encoder. |
| 3 | Service and POST theories cover ASCII `a` repeated 4095, 4096, and 4097 times; first two succeed, last rejects. |
| 4 | Repeat boundary theories with U+00E9 repeated 2047 times plus `a` (4095 bytes), repeated 2048 times (4096), and repeated 2048 times plus `a` (4097). Include U+1F600 repeated 1024 times and with appended `a` to cover surrogate-pair input. Assert independently expected byte counts. |
| 5 | Rejected POST returns 400 with the existing string-result convention; assert exact message under the normal HTTP formatter, not a ProblemDetails object. Blank-input behavior remains unchanged. |
| 6 | Assert error text includes 4096 and UTF-8 bytes, with no echoed input. |
| 7 | Accepted POST cases assert one Encrypt call, unchanged key/token forwarding, base64 of fake ciphertext persisted once, and 200 DTO with original text/id/time. Retain existing retrieval/decryption and pagination tests; add a focused wrapper Decrypt test if needed to pin its byte conversion. |
| 8 | Review diff/changed paths; no infrastructure, deployment, schema, auth, health behavior, or unrelated fixes. |
| 9 | Keep the source and mechanism justification above and beside the named implementation constant. |
| 10 | All new tests run using local doubles, disabled migrations, and dummy configuration; no AWS credentials discovery or live service access. |

Executor checks: run focused tests, then the .NET solution build/test sequence from `.github/workflows/ci-dotnet.yml` with .NET 8 and available dependencies. Restore only when necessary and authorized; it uses package network/cache. Builds/tests write outputs. Inspect existing health-test configuration/environment before running the full suite so it cannot inherit live KMS settings. Do not start the normal application or execute Terraform, deployment, or AWS commands. Review diff, local documentation links, and tracked/untracked paths. Planning itself runs no build/tests.

## Caveats and exclusions

No material human decision is outstanding. This fixed limit applies to the current symmetric direct-KMS contract; a future key/algorithm or encryption architecture change must revisit it. Preserve .NET UTF-8 fallback behavior; do not introduce Unicode normalization or malformed-input policy changes. Existing blank validation still takes precedence for whitespace-only requests. This is not general HTTP request-size/DoS protection, nor proof of deployed AWS or SQL behavior.

Envelope encryption, chunking, external payload storage, authentication, pagination fixes, database durability, environment isolation, IAM, infrastructure, and deployment remain out of scope.

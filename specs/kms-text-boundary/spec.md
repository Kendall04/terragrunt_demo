# Durable Spec — KMS Text Payload Boundary

Status: Approved for technical planning.

## 1. Problem

The current `/text` write path encrypts plaintext directly through AWS KMS.

The application does not currently enforce the effective plaintext-size boundary before attempting the KMS operation.

As a result, oversized input can reach the external encryption dependency and fail there instead of being rejected deterministically by the API.

The application should own this boundary explicitly.

---

## 2. Desired Outcome

Before invoking KMS encryption, the application validates that the plaintext fits within the maximum size supported by the current direct-KMS encryption design.

Input that exceeds that boundary is rejected locally with a clear and deterministic API response.

Valid input at or below the boundary continues through the existing encryption and persistence flow unchanged.

---

## 3. Functional Requirements

### 3.1 Local validation

The size boundary must be evaluated before the KMS encryption request is made.

Oversized input must not depend on AWS/KMS failure behavior for validation.

### 3.2 Byte-based measurement

The boundary is based on the actual encoded plaintext bytes that would be supplied to KMS, not on character count.

The implementation must behave correctly for ASCII and multi-byte Unicode input.

### 3.3 Effective limit

The implementation must use the effective plaintext limit applicable to the repository's current KMS encryption mechanism.

The Planner must determine that limit from the actual implementation and relevant authoritative contract rather than assuming a value from this spec.

### 3.4 API error contract

Oversized plaintext must produce a clear client-visible error using the API's established error conventions.

The exact HTTP status and response shape should remain consistent with the existing API contract unless the repository provides no appropriate convention.

Where compatible with that contract, the response should communicate the maximum allowed plaintext size.

Raw AWS/KMS exceptions must not become the public validation mechanism.

---

## 4. Boundary Behavior

For the effective maximum plaintext size `MAX`:

- `MAX - 1` bytes must be accepted.
- `MAX` bytes must be accepted.
- `MAX + 1` bytes must be rejected before KMS encryption.

Equivalent boundary behavior must be demonstrated with multi-byte UTF-8 input so character count cannot accidentally substitute for byte count.

---

## 5. Existing Behavior to Preserve

For valid input within the supported boundary:

- the existing `/text` behavior remains unchanged;
- encryption continues through the current KMS mechanism;
- ciphertext persistence behavior remains unchanged;
- retrieval/decryption behavior remains unchanged.

This feature must not alter the successful-path encryption architecture.

---

## 6. Scope Boundaries

This feature is limited to making the current direct-KMS plaintext boundary explicit and deterministic.

It does not introduce:

- envelope encryption;
- chunking;
- S3 or other external payload storage;
- alternative encryption architectures;
- authentication or authorization changes;
- Terraform or AWS infrastructure changes;
- deployment-pipeline changes;
- unrelated backend/domain expansion.

Support for larger payloads is a separate future design decision.

---

## 7. Acceptance Criteria

1. Oversized plaintext is rejected before the KMS encryption operation.
2. Size is evaluated using the actual plaintext byte representation used by the current KMS path.
3. `MAX - 1`, `MAX`, and `MAX + 1` boundary behavior is covered by deterministic tests.
4. Multi-byte Unicode input demonstrates that byte size, not character count, controls the boundary.
5. The client receives a clear API error for oversized plaintext using the repository's established error conventions.
6. The maximum supported size is communicated to the client where compatible with the existing error contract.
7. Valid input continues through the existing encryption and persistence flow without behavioral regression.
8. No Terraform, AWS infrastructure, deployment, or unrelated application behavior is changed.
9. The effective KMS plaintext limit and its technical source are identified and justified during planning/implementation.
10. Tests do not require live AWS access merely to validate the boundary behavior.

---

## 8. Planning Boundary

This specification defines required behavior, not implementation structure.

The Planner should inspect the repository to determine:

- the current request/handler/encryption flow;
- the exact byte representation supplied to KMS;
- the effective plaintext limit for the current KMS mechanism;
- existing validation and API error conventions;
- the most appropriate validation boundary;
- existing test abstractions that allow this behavior to be tested without live AWS access.

The Planner may choose implementation details consistent with the repository architecture.

If repository evidence reveals that satisfying this specification would require changing the encryption architecture or public API contract materially, stop and request a human decision rather than expanding scope.

---

## 9. Review Contract

Review the implementation directly against this specification.

The Reviewer must verify the boundary behavior, byte-based semantics, client-visible error behavior, preservation of the valid path, deterministic test evidence, and bounded scope.

A plan-following implementation that does not satisfy this specification is not acceptable.

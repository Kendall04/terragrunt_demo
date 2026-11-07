# V2 architecture review: historical design

The October 16 design review is superseded by the implemented
[V2 atlas](../../docs/interactive/V2-INDEX.md),
[technical audit](../../docs/ENGINEERING-REVIEW.md) and
[CI/CD review](../../docs/CI-CD-REVIEW.md).

Its recommendations preceded strict SQL TLS, hourly backups, cold SAME/CROSS-AZ
recovery, Sentinel installation and public static hosting. They are not current
installation status. The complete original remains available at
[immutable Git source](https://github.com/Kendall04/terragrunt_demo/blob/24cd87c0a780fe398d46553ee8c539bdd32eafa5/terraform/docs/v2-architecture-review.md).
This short bridge preserves existing local qualification links without changing
their historical manifests or claiming a new qualification.

<a id="5-integración-service-identity-pki"></a>

## Historical PKI proposal

Service Identity PKI was a separate integration proposal, not an ECS completion
requirement. The original proposal is retained in the immutable source above;
the current ECS trust boundary is documented in the V2 atlas.

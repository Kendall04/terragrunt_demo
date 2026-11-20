# Portfolio applications

The current public application is **[ECS Cloud Resilience Laboratory](https://d20ioz705caon7.cloudfront.net/)**.
Use [product/README.md](product/README.md) for DEMO, supervised local AWS Edition,
static packaging and tests; [HOSTING.md](product/HOSTING.md) covers publication/rollback.

```sh
node portfolio/product/server.mjs
# http://127.0.0.1:4182/
```

The current Architecture Explorer presents five ECS diagrams and twelve historical
snapshots. [The atlas](../docs/interactive/CURRENT-INDEX.md) records sources,
authenticated Archify 3.1.0 generation and visual checks. Static DEMO has no AWS
API dependency and no deployment credentials.

## Preserved local portfolio

`portfolio/server.mjs`, `index.html` and the associated contracts are the earlier
local-only presentation. They remain because tests and historical evidence paths
use them; they are not the current public site. Its five original diagrams and
source-document routes retain V1, prepared-target recovery and Sentinel experiments.

```sh
node portfolio/server.mjs
```

Use the address printed by that server. Its synthetic states are not live AWS
telemetry. The original narrative is recoverable in
[Git history](https://github.com/Kendall04/terragrunt_demo/blob/1a39c46cc02f262c04f438207647acc1282393a0/portfolio/README.md);
actual experiment records remain linked through the [history index](../docs/history/README.md).

Both presentations retain source provenance, CSP/sandbox isolation and existing
contract tests. No package, diagram or public site was regenerated for the
18 November documentation consolidation.

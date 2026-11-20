# ECS Cloud Resilience Laboratory

[Product documentation](product/README.md) covers DEMO, supervised local AWS
Edition and browser tests. [Hosting](product/HOSTING.md) covers static packaging,
publication and rollback.

```sh
node portfolio/product/server.mjs
# http://127.0.0.1:4182/
node --test portfolio/test-contract.mjs
```

Architecture Explorer includes only the [five final diagrams](../docs/interactive/CURRENT-INDEX.md).
The old local portfolio and twelve historical diagrams are no longer shipped.
The existing CI entrypoint now tests the current product, including security
mutants, CSP, iframe isolation, source hashes and routing.

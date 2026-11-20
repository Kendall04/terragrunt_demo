# Archify architecture atlas

The **five current ECS diagrams** are indexed in
[CURRENT-INDEX.md](CURRENT-INDEX.md) and published in the
[Architecture Explorer](https://d20ioz705caon7.cloudfront.net/architecture).
They explain the final platform, automatic DEV delivery, networking/E13,
SQL recovery and trust boundaries. PROD is not installed or validated.

## Historical collections

Twelve snapshots remain separate from the current architecture:

| Collection | Contents and provenance |
| --- | --- |
| Seven V2 views, 6 November 2026 | [Historical V2 index](V2-INDEX.md), [generation](GENERATION-V2.json), [traceability](TRACEABILITY-V2.json), [audit](V2-AUDIT.md) and [validation](V2-VALIDATION.md). Includes the former Sentinel runtime and pre-automatic-delivery state. |
| Five earlier views | [V1 platform](v1-platform.html), [V1 network](v1-network.html), [prepared-target recovery](az6-recovery.html), [local backup signals](backup-signals.html), [retired Sentinel integration experiment](future-integrations.html). [Generation](GENERATION.json) and [pins](../../portfolio/archify-pins.json) preserve their original scope. |

Sentinel's [AWS runtime was retired](../SENTINEL-RETIREMENT.md) on 10 November.
Historical diagrams preserve what was implemented or proposed on their stated
date; they are not live telemetry or current operational dependencies.

## Sources, generation and viewing

Editable JSON, original generated HTML and enlarged reading alternatives remain
under `source/`, this directory and `readable/`. All use authentic **Archify 3.1.0**,
commit `1c2b42d660e4a7571813fb43839c79e3e9ca7720`, with the original
[MIT license](ARCHIFY-LICENSE.txt). Manifests identify input commits, tool hashes,
outputs and validation receipts. Do not patch generated HTML or update hashes
without official regeneration and review.

[Current generation instructions](CURRENT-INDEX.md#procedencia-y-regeneración)
are the maintained procedure. Historical regeneration requires its original
source revision; it is not part of routine documentation cleanup.
The portfolio serves isolated presentation copies with CSP, an opaque iframe,
zoom/pan/fit and a text reading alternative. Original artifacts remain intact.
The [legacy local portfolio](../../portfolio/README.md) exists for its historical
evidence path; `portfolio/product` is the current public application.

"""Inert, digest-pinned source data; never a Terraform root or AWS authority.

The original paths are historical identifiers. Only explicit generators select
ordinary declarations from the text; accepted TARGET package bytes stay fixed.
"""
import json
from pathlib import Path

ARCHIVE = 'ci/authority/retired'
MANIFEST = 'ci/authority/target/legacy-sources.json'


def archived(name):
    return ARCHIVE + '/' + name + '.txt'


def source(root, name):
    return Path(root) / archived(name)


def sources(root, prefix):
    manifest = json.loads((Path(root) / MANIFEST).read_text())
    return [(name[len(prefix) + 1:], source(root, name))
            for name in sorted(manifest['sources']) if name.startswith(prefix + '/') and name.endswith('.tf')]

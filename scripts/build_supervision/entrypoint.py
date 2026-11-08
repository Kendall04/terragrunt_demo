"""Fixed protected-host entry points; ports/context are never read from payload JSON.

WP3C supplies authenticated adapters and isolation. There is deliberately no dynamic
module/plugin selector, environment bootstrap, AWS discovery or direct CLI launch.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/build_supervision'))
sys.path.insert(0, str(ROOT / 'scripts/qualification'))


def build(context, control, payload, images, manifests, records, wakeup):
    from supervisor import Supervisor
    return Supervisor(context, control, payload, images, manifests, records).run(wakeup)


def finalize(account, region, evidence, qualifications, wakeup):
    from finalizer import Finalizer
    return Finalizer(account, region, evidence, qualifications).finalize(wakeup)


if __name__ == '__main__':
    raise SystemExit('E1_PROTECTED_HOST_ADAPTERS_REQUIRED; no standalone activation')

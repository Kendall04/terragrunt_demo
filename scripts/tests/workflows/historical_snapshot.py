"""Only the owner-approved two-ref delta may normalize historical snapshots.

The retained historical whole-authority digests are not replaced. Any other
field, identity, source hash, or activation remains visible to those assertions.
"""
import copy

REF='refs/heads/codex/final-github-actions-cicd'
SOURCE_PAIRS={'scripts/workflow_requests/contract.py': ('c69368c01e5eced55fb33c55ed7592cee1799ba77a6b6765a16bf2fc40338fc7', 'c1f41c8cc1fadc8b820c4c127e776937a30ba27f70ef16de1112b23c6d9d806e'), 'scripts/workflow_requests/render.py': ('68bbe212d68f848f5b444b4355282a785da32506f9c937f39b4d4e356b464491', '3f82a50f2948a6c6cf00cc53061c95506a7a9d3760f0fc3e54ba75993e1a9468'), '.github/workflows/e1-release.yml': ('03bae05bfd5b85d8be0a3fbce31c4eb814c43ba5e415e953727f948072508337', 'e11b079eb937662d2f5603fb573dd14e924f25c0f3c763566ccae90072d6dc2b'), '.github/workflows/e1-dev-deploy.yml': ('8d4e6bdd74ff74d3ec2cf16df06810df21c114a2f58adf121c73ededffa004da', 'd8049cc260380bd1be0d2b914580c615eece8c0bc80e227f6adab7b6119b65f6')}

def before_authorized_trial(authority):
    value=copy.deepcopy(authority)
    from scripts.tests.security_root.wp6 import dev_trial_approvals
    dev_trial_approvals(value)
    value['wp6']['approvals']={}
    # Preserve the prior immutable snapshot while checking the exact approved DEV delta.
    for key,(previous,current) in {'normal-delivery/deploy-dev': ('9a56022ea676cc583fc9e5eaec292ea2cc9f6434131d2cd3a21c95096f792577', 'ed34067952fc32d657ba42feb6fb55e45bffe8e9991877c1b670331483fd0cee'), 'cleanup-recovery/cleanup-dev': ('2a4b6681a62824b69ba127f33fda22cca85398647777b0a91041e4a2ba6ef312', 'ea8c36cf06cdc483aab3b3ff4da0578b3fbb7660423b6abd9804c9cc8de5c595')}.items():
        assert value["wp4d"]["selected"][key]["package_sha256"]==current
        value["wp4d"]["selected"][key]["package_sha256"]=previous
    assert value['wp4d']['selected']['request-gateway/deploy-dev']['package_sha256']=='867decc33be9e95215767103ecb3b9ca10b2f89653bed365c39c2410c1332037'
    value['wp4d']['selected']['request-gateway/deploy-dev']['package_sha256']='2ac570048cc68d3a88013f45dbd5c71d3fc0145a3a0a18542c138eb19de2643d'
    for key in ('release','deploy-dev'):
        assert value['wp6']['selected'][key]['ref']==REF
        value['wp6']['selected'][key]['ref']='refs/heads/develop'
    for path,(previous,current) in SOURCE_PAIRS.items():
        assert value['wp6']['source_sha256'][path]==current,path
        value['wp6']['source_sha256'][path]=previous
    return value

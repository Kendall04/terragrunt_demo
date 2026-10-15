"""Only the owner-approved two-ref delta may normalize historical snapshots.

The retained historical whole-authority digests are not replaced. Any other
field, identity, source hash, or activation remains visible to those assertions.
"""
import copy

REF='refs/heads/codex/final-github-actions-cicd'
SOURCE_PAIRS={'scripts/workflow_requests/contract.py': ('c69368c01e5eced55fb33c55ed7592cee1799ba77a6b6765a16bf2fc40338fc7', 'c1f41c8cc1fadc8b820c4c127e776937a30ba27f70ef16de1112b23c6d9d806e'), 'scripts/workflow_requests/render.py': ('68bbe212d68f848f5b444b4355282a785da32506f9c937f39b4d4e356b464491', '1f28b7f1bfefdaaae7f6ee6bae974d5120c5825e7963deb2fd9ef468c9041748'), '.github/workflows/e1-release.yml': ('03bae05bfd5b85d8be0a3fbce31c4eb814c43ba5e415e953727f948072508337', 'e11b079eb937662d2f5603fb573dd14e924f25c0f3c763566ccae90072d6dc2b'), '.github/workflows/e1-dev-deploy.yml': ('8d4e6bdd74ff74d3ec2cf16df06810df21c114a2f58adf121c73ededffa004da', 'd8049cc260380bd1be0d2b914580c615eece8c0bc80e227f6adab7b6119b65f6')}


# Exact source-transport content IDs only. Original historical digest assertions stay intact.
SOURCE_TRANSPORT_BUNDLES={'request-gateway': ('792a67db8f5bda0f97569a82a05f095418def6a7379dcaa54203201d654dec4f', 'c9c9eb51a941f84e37e128a8176d46741a248c6c4b49959058188398456a4b7b'), 'status': ('60c0cd23933479a0935ccbba399f78086e303defe6bbaaae7607d5e8b23650fa', 'e2df102912bf4c302c8a7e1cb3951b97c1219a1c7e26234b05dfe4eb02890684')}
SOURCE_TRANSPORT_SELECTED={('internal_release', 'request-gateway/release', 'bundle_digest'): ('792a67db8f5bda0f97569a82a05f095418def6a7379dcaa54203201d654dec4f', 'c9c9eb51a941f84e37e128a8176d46741a248c6c4b49959058188398456a4b7b'), ('internal_release', 'status/status-neutral', 'bundle_digest'): ('60c0cd23933479a0935ccbba399f78086e303defe6bbaaae7607d5e8b23650fa', 'e2df102912bf4c302c8a7e1cb3951b97c1219a1c7e26234b05dfe4eb02890684'), ('wp4d', 'request-gateway/deploy-dev', 'package_sha256'): ('867decc33be9e95215767103ecb3b9ca10b2f89653bed365c39c2410c1332037', 'e113ae86c672bb19428dde8fcb0088a5773898bff4c2b2eaeeee2b4559201fe5'), ('wp4d', 'request-gateway/promote-prod', 'package_sha256'): ('71ceed130c8ae20bdb9a0727da9c2895b7027c9433e61be323cd3b58bea8ef8b', '8953dab965477d8a810d51a9b68c89c022c0a5fa1a9ca2fda38de4fad4669c49'), ('wp4d', 'request-gateway/emergency-dev', 'package_sha256'): ('77f188b6fc85736525322c33a0b31450595182f01eff1ce38f3f0d9ebbaa6448', '4182da3d2a11137b7614a42cf78e1648af620b6e2af4601f4ef8902e897c7882'), ('wp4d', 'request-gateway/emergency-prod', 'package_sha256'): ('1293465a2deba9209ab0e8ad75a4d7f51f1bc4d7eaf50aac638e35b34a469d84', 'bbb8917819044f97af866661ed51366c84ebf99f8a7745ea57d9ae5e30bb5594'), ('wp5', 'request-gateway/infra-dev', 'package_sha256'): ('e579f74fd664404a78307e9d1be0f1e144f1a0926984bef0daa27902beca0168', '05cba0c2eb61b8c5174033f3493abe4264ce2f6a19b2e08bb83d20e6b2c797c5'), ('wp5', 'request-gateway/infra-prod', 'package_sha256'): ('f94752258b600dc0d8860720c92708023a5c5915b9a7ae5c2599bc23b1a14597', 'bff1c10241fab18d11fad9ed94e036ec51f6c473f5d8b1b3e7e1bc09b899800e'), ('wp5', 'request-gateway/infra-high-risk-dev', 'package_sha256'): ('3475d56fa72380e1feee8d659f51aad1311258e76a75c24ab4a22687710a0f45', '635b36664d6855e450cb6a00bd1b44e815ff689d9d56d400e52f8a0614cf764c'), ('wp5', 'request-gateway/infra-high-risk-prod', 'package_sha256'): ('30da01fd8d7c64b5d2b40297df6e873eea41d85d2a018b7a8fa96d845f3c59e3', '34db0c081229e0046939c318b936795a8b0086a21de7256fb85bbe8c305dae36')}
SOURCE_TRANSPORT_SUPPORT=('16aaf048b63c322b151ee9a183b597481eccf9d12bbe3e544eb93e67bb4821eb', '2083e148541eceb18d82d481377c80267e0cf13921c321817acca72353f358e0')

def before_source_transport(value):
    for name, (previous, current) in SOURCE_TRANSPORT_BUNDLES.items():
        assert value['control_bundles']['classes'][name]['sha256'] == current
        value['control_bundles']['classes'][name]['sha256'] = previous
        for ref in value['control_bundles']['consumer_references'].values():
            if ref['class'] != name:
                continue
            for field, prefix, suffix in (('sha256', '', ''), ('bundle_id', 'sha256:', ''),
                                          ('key', 'bundles/sha256/', '.json')):
                assert ref[field] == prefix + current + suffix
                ref[field] = prefix + previous + suffix
    for (group, key, field), (previous, current) in SOURCE_TRANSPORT_SELECTED.items():
        assert value[group]['selected'][key][field] == current
        value[group]['selected'][key][field] = previous
    previous, current = SOURCE_TRANSPORT_SUPPORT
    assert value['internal_release']['support_sha256'] == current
    value['internal_release']['support_sha256'] = previous
    return value


def before_authorized_trial(authority):
    value=before_source_transport(copy.deepcopy(authority))
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

"""WP4A-N1 acceptance assertion; canonical runtime semantics are unchanged."""
from scripts.normal_delivery import authorization as a


def validate(model=None):
    m = a.MODEL if model is None else model
    task = m['canonical_task']
    a.require(set(task) == set(m['task_required']))
    a.require(len(task['containerDefinitions']) == 2)
    groups = [(set(task), set(m['forbidden_task']), set(m['task_return_only']),
               set(m['task_defaults']))]
    for kind, container in zip(('app', 'probe'), task['containerDefinitions']):
        a.require(set(container) == set(m['container_required'][kind]))
        groups.append((set(container), set(m['forbidden_container']), set(), set()))
    groups.append((set(m['service_required']) | {'desiredCount', 'taskDefinition'},
                   set(m['forbidden_service']), set(m['service_return_only']), set()))
    a.require(groups[-1][0] == set(m['service_ownership']))
    env_fields = {'cluster', 'service', 'platformVersion', 'networkConfiguration', 'loadBalancers'}
    for field, owner in m['service_ownership'].items():
        expected = ('ENVIRONMENT_CONFIGURATION' if field in env_fields else
                    'BOUNDED_NON_SECURITY_DYNAMIC' if field == 'desiredCount' else
                    'RETURN_ONLY_AUTHORIZED_REVISION' if field == 'taskDefinition' else 'SECURITY_ROOT_OWNED')
        a.require(owner == expected)
    for key in ('forbidden_task', 'forbidden_container', 'forbidden_service',
                'task_return_only', 'service_return_only', 'service_required'):
        a.require(len(m[key]) == len(set(m[key])))
    for required, forbidden, returned, defaults in groups:
        a.require(not (required & forbidden or required & returned or forbidden & returned
                       or required & defaults or forbidden & defaults or returned & defaults))
    a.require(not set(m['container_defaults']) & set(m['forbidden_container']))
    # Ownership names must still describe the actual binding positions, not merely
    # cover the same vocabulary. Constants cannot be relabeled caller-controlled.
    def dynamic(node):
        if type(node) is dict:
            return '$binding' in node or any(dynamic(v) for v in node.values())
        return type(node) is list and any(dynamic(v) for v in node)
    for key, value in task.items():
        expected = ('MIXED_CLOSED_CONTAINER_MODEL' if key == 'containerDefinitions' else
                    'ENVIRONMENT_CONFIGURATION' if dynamic(value) else 'SECURITY_ROOT_OWNED')
        a.require(m['task_required'][key] == expected)
    for kind, container in zip(('app', 'probe'), task['containerDefinitions']):
        for key, value in container.items():
            expected = ('QUALIFIED_RELEASE_DERIVED' if key == 'image' else
                        'ENVIRONMENT_CONFIGURATION' if dynamic(value) else 'SECURITY_ROOT_OWNED')
            a.require(m['container_required'][kind][key] == expected)

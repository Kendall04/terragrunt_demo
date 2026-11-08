"""WP4D adapter obligations; no SDK implementation or invocation activation.

Ports are injected only by installed protected wiring, never caller data. Every
observation is a new independently authoritative read, not cached event payload.
Methods must honor their absolute deadline and sanitize diagnostics. Storage uses
normal_delivery.delivery.Records. A subclass is an interface, not authentication.
"""
from abc import ABC, abstractmethod


class Effects(ABC):
    @abstractmethod
    def now(self):
        """Trusted integer monotonic operation clock."""
        raise NotImplementedError

    @abstractmethod
    def effect(self, token, deadline):
        """WP4B envelope: token/request_sha256/state/result.

        APPLIED requires independent observation of exact operation attribution
        AND the closed mutation result. An ACK or matching resource alone cannot
        prove attribution. ABSENT requires authoritative non-application; UNKNOWN
        covers incomplete/ambiguous evidence. No polling past the deadline.
        """
        raise NotImplementedError

    @abstractmethod
    def mutate(self, stage, token, request, deadline):
        """Dispatch ONLY the installed domain's closed action vocabulary.

        No generic AWS request proxy. A lost ACK is not a reason to retry. The
        journal calls this once after durable plan/attempt and fresh guards.
        """
        raise NotImplementedError


class ApplicationRuntime(Effects):
    @abstractmethod
    def config(self):
        """Authenticated current env colors, cleanup rule, success-history refs.

        Resource positions must be security-controller published (WP4A vocabulary).
        Cleanup rule is the existing environment scale-down schedule; target ID
        is exactly scale-down. Emergency schedule uses that existing algorithm's
        bounded delay and installed cleanup function, not caller-selected code.
        """
        raise NotImplementedError

    @abstractmethod
    def observe(self, operation, deadline):
        """Fresh ECS/ALB snapshot with exact task, service and target health.

        Normalize only single 100%-weight forwarding to the installed target.
        Reject duplicate/weighted/unknown mappings. stable means ECS completed
        deployment of the selected revision, with no mixed revision cohort.
        Target IDs must belong to those exact running tasks and target group;
        include every required target, never filter unhealthy targets. The
        operation/environment bind the read, not event-supplied health claims.
        Task/settings use WP4A's authoritative describe normalization.
        """
        raise NotImplementedError


class NatRuntime(Effects):
    @abstractmethod
    def context(self, action, deadline):
        """Protected membership plus independently described EC2/ASG state.

        Protected publication binds the exact instance to an approved ASG slot,
        subnet/AZ/VPC, EIP, RT and ENI, and resolved numeric launch version/AMI,
        user-data digest, profile/role, SG and metadata specification. Event IDs,
        prefix, names and Role=nat tags cannot create this membership. Read exact
        InService/Healthy ASG membership and ENI attachment; do not pick the first
        instance. Publish a new operation for a different replacement instance.
        Route absence selects create_route; known presence selects replace_route.
        Do not fallback/resend after an ambiguous mutation acknowledgement.
        """
        raise NotImplementedError

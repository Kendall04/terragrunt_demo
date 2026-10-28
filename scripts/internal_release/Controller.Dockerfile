# Offline assembly recipe. BASE is a separately reviewed digest-pinned image
# containing Python 3.10+, boto3 and awslambdaric. No dependency download here.
ARG BASE
FROM ${BASE}
WORKDIR /opt/e1
COPY scripts/internal_release/e1_contract.py scripts/internal_release/e1_contract.py
COPY scripts/internal_release/exchange.py scripts/internal_release/exchange.py
COPY scripts/internal_release/publisher.py scripts/internal_release/publisher.py
COPY scripts/internal_release/workers.py scripts/internal_release/workers.py
COPY scripts/internal_release/adapters.py scripts/internal_release/adapters.py
COPY scripts/internal_release/services.py scripts/internal_release/services.py
COPY scripts/internal_release/runtime.py scripts/internal_release/runtime.py
COPY scripts/internal_release/worker.py scripts/internal_release/worker.py
COPY scripts/build_supervision/supervisor.py scripts/build_supervision/supervisor.py
COPY scripts/qualification/finalizer.py scripts/qualification/finalizer.py
COPY ci/schemas/e1-build-attempt.schema.json ci/schemas/e1-build-attempt.schema.json
COPY ci/schemas/e1-qualification.schema.json ci/schemas/e1-qualification.schema.json
COPY ci/schemas/release-manifest.schema.json ci/schemas/release-manifest.schema.json
COPY terraform/infra/security/authority.json terraform/infra/security/authority.json
ENV PYTHONPATH=/opt/e1/scripts/internal_release
RUN python3 -c "import boto3, awslambdaric"
ENTRYPOINT ["python3", "-m", "awslambdaric"]
CMD ["runtime.handler"]

# BASE is an admin-reviewed immutable image with Python and, according to the
# worker binding, .NET SDK 8 or Docker/buildx/containerd. No controller code/SDK.
ARG BASE
FROM ${BASE}
COPY scripts/internal_release/worker.py /opt/e1/scripts/internal_release/worker.py
RUN python3 -c "import urllib.request"
# CodeBuild replaces ENTRYPOINT. Probe execution overrides the environment image
# with the controller-published application digest, using service pull credentials.

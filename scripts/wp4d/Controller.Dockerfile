# Administrator supplies an observed, immutable AWS Lambda Python base digest.
ARG BASE
FROM ${BASE}
COPY scripts/wp4d/runtime.py /var/task/runtime.py
COPY scripts/wp4d/installed.py /var/task/installed.py
RUN python3 -c "import boto3, awslambdaric"
CMD ["runtime.handler"]

# Offline assembly only; registry push/runtime installation are separate gates.
FROM docker.io/library/python@sha256:4cea12ab7d78a3312c85f8cab19b6971d4fe9704da25443986c0bc20a6678850
ARG SOURCE_DATE_EPOCH
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_CONFIG_FILE=/dev/null \
    PYTHONPATH=/opt/e1/deps \
    PATH=/opt/e1/deps/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /opt/e1
COPY requirements.lock /opt/e1/requirements.lock
RUN --mount=type=bind,source=wheels,target=/wheels,readonly \
    python3 -m pip install --no-index --find-links=/wheels --require-hashes \
      --no-cache-dir --no-compile --disable-pip-version-check \
      --target=/opt/e1/deps -r /opt/e1/requirements.lock && \
    python3 -m pip check && \
    python3 -c "import os; t=int(os.environ['SOURCE_DATE_EPOCH']); [(os.utime(os.path.join(root,n),(t,t),follow_symlinks=False)) for root,dirs,files in os.walk('/opt/e1/deps') for n in dirs+files]; os.utime('/opt/e1/deps',(t,t))"
COPY jq /usr/local/bin/jq
RUN chmod 0555 /usr/local/bin/jq
COPY scripts/wp4d/runtime.py scripts/wp4d/runtime.py
COPY scripts/wp4d/installed.py scripts/wp4d/installed.py
RUN python3 -c "import boto3,botocore,shutil; assert all(shutil.which(v) for v in ('bash','aws','jq','sha256sum','date','python3','env'))"
ENTRYPOINT []
CMD ["python3", "/opt/e1/scripts/wp4d/runtime.py"]

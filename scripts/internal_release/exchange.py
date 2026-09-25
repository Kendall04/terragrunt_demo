"""Exact attempt-scoped S3 capabilities. Worker bytes are never evidence.

The injected client is an SDK S3 client in the trusted controller. No worker
receives it or credentials; a presigned request authorizes one method/object.
"""
import base64
import json
from e1_contract import canonical, closed, digest, operation_id, require, version


class Exchange:
    def __init__(self, s3, bucket, attempt):
        self.s3, self.bucket = s3, bucket
        self.prefix = 'quarantine/demo-api/' + operation_id(attempt) + '/'

    def source(self, nodes, worker):
        require(worker in ('dotnet', 'image'))
        raw = canonical([[p, kind, mode, base64.b64encode(content).decode()]
                         for p, kind, mode, content in nodes])
        key = self.prefix + worker + '/source-' + digest(raw) + '.json'
        receipt = self.s3.put_object(Bucket=self.bucket, Key=key, Body=raw,
            IfNoneMatch='*', ChecksumSHA256=base64.b64encode(bytes.fromhex(digest(raw))).decode())
        exact = version(receipt.get('VersionId'))
        back = self.s3.get_object(Bucket=self.bucket, Key=key, VersionId=exact)
        require(back.get('VersionId') == exact and back['Body'].read(len(raw) + 1) == raw)
        return self.s3.generate_presigned_url('get_object', Params={
            'Bucket': self.bucket, 'Key': key, 'VersionId': exact}, ExpiresIn=900, HttpMethod='GET')

    def output(self):
        # The condition is a signed header, not an optional worker convention.
        return self.s3.generate_presigned_url('put_object', Params={
            'Bucket': self.bucket, 'Key': self.prefix + 'image/output.oci',
            'IfNoneMatch': '*'}, ExpiresIn=900, HttpMethod='PUT')

    def selected_output(self):
        key = self.prefix + 'image/output.oci'
        # Single create-only key; resolve through trusted S3, never worker metadata.
        head = self.s3.head_object(Bucket=self.bucket, Key=key)
        exact = version(head.get('VersionId'))
        require(0 < head['ContentLength'] <= 1024 * 1024 * 1024)
        value = self.s3.get_object(Bucket=self.bucket, Key=key, VersionId=exact)
        raw = value['Body'].read(head['ContentLength'] + 1)
        require(value.get('VersionId') == exact and len(raw) == head['ContentLength'])
        return {'bucket': self.bucket, 'key': key, 'version_id': exact,
                'sha256': digest(raw), 'bytes': raw}

"""Parse OCI data without extracting or executing it; upload via ECR APIs.

No Docker daemon, subprocess, plugin or application code in the publisher.
Only single-image OCI archives with digest-checked referenced blobs are admitted.
"""
import hashlib
import io
import json
import tarfile
from e1_contract import digest, require


def oci(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 1024 * 1024 * 1024)
    files = {}
    directories = set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            if member.isdir():
                require(member.name in ('blobs', 'blobs/sha256') and member.name not in directories)
                directories.add(member.name)
                continue
            require(member.isfile() and member.name not in files and len(files) < 1024)
            require(member.name in ('index.json', 'oci-layout') or
                    (member.name.startswith('blobs/sha256/') and len(member.name) == 77
                     and all(c in '0123456789abcdef' for c in member.name[13:])))
            require(0 <= member.size <= len(raw))
            files[member.name] = archive.extractfile(member).read(member.size + 1)
            require(len(files[member.name]) == member.size)
    require(json.loads(files['oci-layout']) == {'imageLayoutVersion': '1.0.0'})
    index = json.loads(files['index.json'])
    require(index.get('schemaVersion') == 2 and len(index.get('manifests', [])) == 1)
    used = {'index.json', 'oci-layout'}
    def blob(descriptor):
        identity = descriptor.get('digest', '')
        require(identity.startswith('sha256:') and len(identity) == 71)
        key = 'blobs/sha256/' + identity[7:]
        content = files[key]
        require(digest(content) == identity[7:] and len(content) == descriptor.get('size'))
        used.add(key)
        return content
    descriptor = index['manifests'][0]
    require(descriptor.get('mediaType') == 'application/vnd.oci.image.manifest.v1+json')
    manifest = blob(descriptor)
    decoded = json.loads(manifest)
    require(decoded.get('schemaVersion') == 2)
    require(decoded['config'].get('mediaType') == 'application/vnd.oci.image.config.v1+json')
    config = blob(decoded['config'])
    meta = json.loads(config)
    require(meta.get('os') == 'linux' and meta.get('architecture') == 'amd64')
    layers = decoded.get('layers', [])
    require(0 < len(layers) <= 128)
    blobs = [(decoded['config']['digest'], config)]
    for layer in layers:
        require(layer.get('mediaType') in ('application/vnd.oci.image.layer.v1.tar',
                                          'application/vnd.oci.image.layer.v1.tar+gzip'))
        require(not set(layer) & {'urls', 'data'})
        blobs.append((layer['digest'], blob(layer)))
    require(set(files) == used)
    return manifest, blobs


def publish(ecr, repository, raw):
    manifest, blobs = oci(raw)
    for identity, content in blobs:
        started = ecr.initiate_layer_upload(repositoryName=repository)
        upload = started['uploadId']
        size = started['partSize']
        require(type(size) is int and 5 * 1024 * 1024 <= size <= 20 * 1024 * 1024)
        for offset in range(0, len(content), size):
            part = content[offset:offset + size]
            ecr.upload_layer_part(repositoryName=repository, uploadId=upload,
                partFirstByte=offset, partLastByte=offset + len(part) - 1, layerPartBlob=part)
        try:
            finished = ecr.complete_layer_upload(repositoryName=repository,
                                                 uploadId=upload, layerDigests=[identity])
            require(finished.get('layerDigest') == identity)
        except Exception as exc:
            # ECR validates the supplied content address. Existing base layers
            # are routine across images; final PutImage still validates references.
            require(getattr(exc, 'response', {}).get('Error', {}).get('Code') == 'LayerAlreadyExistsException')
    expected = 'sha256:' + digest(manifest)
    try:
        result = ecr.put_image(repositoryName=repository, imageManifest=manifest.decode('utf-8'),
                              imageManifestMediaType='application/vnd.oci.image.manifest.v1+json')
    except Exception as exc:
        require(getattr(exc, 'response', {}).get('Error', {}).get('Code') == 'ImageAlreadyExistsException')
        observed = ecr.batch_get_image(repositoryName=repository, imageIds=[{'imageDigest': expected}],
                                      acceptedMediaTypes=['application/vnd.oci.image.manifest.v1+json'])
        require(not observed.get('failures') and len(observed.get('images', [])) == 1)
        result = {'image': observed['images'][0]}
        require(result['image'].get('imageManifest', '').encode() == manifest)
    image = result['image']
    require(image.get('repositoryName') == repository)
    identity = image['imageId']['imageDigest']
    require(identity == expected)
    return identity

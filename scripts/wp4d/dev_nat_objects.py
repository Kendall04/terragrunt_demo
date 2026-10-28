"""DEV NAT-only bounded absent-key observation; selected by its exact package.

No cloud calls on import. Base WP4/PROD storage behavior remains unchanged.
"""
from scripts.wp4d.adapters import Objects as BaseObjects, _require


class NatObjects(BaseObjects):
    def read(self, key):
        try:
            return super().read(key)
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code not in ("AccessDenied", "403"):
                raise
            key_name = self._key(key)
            # GetObject 403 is never absence evidence. An authorized exact-prefix
            # listing must independently prove absence; denied/partial/present
            # observations propagate the original failure or a fixed rejection.
            listed = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=key_name, MaxKeys=2)
            _require(listed.get("IsTruncated") is False
                     and listed.get("Prefix") == key_name
                     and type(listed.get("Contents", [])) is list)
            contents = listed.get("Contents", [])
            _require(all(type(item) is dict and type(item.get("Key")) is str
                         and item["Key"].startswith(key_name) for item in contents))
            if not any(item["Key"] == key_name for item in contents):
                return None
            raise

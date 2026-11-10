# SQL backup storage tools

These helpers belong to SQL backup/recovery, independently of Sentinel:

- `storage_verification.py`: reads the exact S3 versions, checks SSE-KMS,
  manifest schema, length and SHA-256. The producer's native checksum receipt
  does not replace a fresh SQL `RESTORE VERIFYONLY` or a full restore.
- `backup_retention.py`: plans bounded admission of verified older pairs to
  the existing seven-day Lifecycle rule. Keeps the newest two pairs; never
  deletes objects. Applying its plan changes version tags and requires approval.
- `backup_restore_pin.py`: copies and verifies the selected pair outside the
  Lifecycle prefix before recovery. Creates restore-hold objects; no SQL mutation.

The functions and tests were extracted from `operations/integrations/portable`
at `528a583d4f74ccd0368cf00929b7315d582cdb35`. No Lambda, observation schedule,
EventBridge publisher or Sentinel journal is needed to use them. The hourly
producer remains `host.py` plus `sql-backup.timer`; this extraction does not
reinstall or change the running producer.

The retired observer used to perform retention admission. No replacement
automatic tagger is installed by the separation. Existing Lifecycle rules still
expire previously admitted versions; untagged new backups can accumulate cost.
Review and explicitly apply a bounded plan when retention maintenance is needed.
Retain the CMK and restore holds until their recovery policy is decided.

Offline tests, without AWS:

```sh
python3 -I -B -m unittest discover -s operations/sql-backup/storage -v
```

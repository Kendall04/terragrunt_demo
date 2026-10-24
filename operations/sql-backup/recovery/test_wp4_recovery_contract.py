"""Expose the same V2 contract tests to the explicit recovery CI, no duplication."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from scripts.tests.normal_delivery.test_recovery_v2 import RecoveryV2Tests

# Historical receipt projection is gap reporting, never native approval.
from test_receipt_gaps import ReceiptGapTests

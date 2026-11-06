import unittest
from collect_continuity import summarize, timestamp


def sample(second, healthy=1, state='HEALTHY_ACTIVE', failures=0):
    return {'timestamp': second*1000, 'eventId': str(second),
            'data': {'healthy': healthy, 'activePermanentFailures': failures, 'result': {'state': state}}}


class ContinuityTests(unittest.TestCase):
    def test_unhealthy_cycle_splits_interval_without_erasing_it(self):
        r = summarize([sample(0), sample(60), sample(120, 0, 'STALLED'), sample(180), sample(240)])
        self.assertEqual([x['observedSeconds'] for x in r['healthySegments']], [60, 60])
        self.assertEqual(r['unhealthySamples'][0]['state'], 'STALLED')

    def test_gap_is_unknown_not_interpolated_health(self):
        r = summarize([sample(0), sample(60), sample(240), sample(300)])
        self.assertEqual(len(r['healthySegments']), 2)
        self.assertEqual(r['visibilityGaps'][0]['seconds'], 180)

    def test_single_sample_is_zero_duration_and_missing_failure_visibility_fails_closed(self):
        self.assertEqual(summarize([sample(5)])['healthySegments'][0]['observedSeconds'], 0)
        self.assertFalse(summarize([sample(5, failures=None)])['healthySegments'])

    def test_duplicates_are_not_extra_evidence_and_unknown_is_not_healthy(self):
        with self.assertRaises(ValueError): summarize([sample(0), sample(0)])
        self.assertFalse(summarize([sample(0, state='UNKNOWN')])['healthySegments'])

    def test_utc_is_required(self):
        self.assertEqual(timestamp('2026-11-06T09:52:00Z').hour, 9)
        with self.assertRaises(ValueError): timestamp('2026-11-06T09:52:00-06:00')


if __name__ == '__main__': unittest.main()

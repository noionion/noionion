"""Regression checks for account counters, missing dates and public export boundaries."""
from datetime import date
import unittest
from xml.etree import ElementTree as E

from codex_usage import N, panel, sanitize, validate


class UsageTests(unittest.TestCase):
    def response(self):
        return {'summary': {'lifetimeTokens': 1000, 'peakDailyTokens': 800,
                            'currentStreakDays': 2, 'longestStreakDays': 3,
                            'email': 'private@example.invalid'},
                'dailyUsageBuckets': [{'startDate': '2026-10-24', 'tokens': 0},
                                      {'startDate': '2026-10-25', 'tokens': 800}],
                'accountId': 'must-not-be-published', 'accessToken': 'must-not-be-published'}

    def snapshot(self):
        return sanitize(self.response(), '2026-10-25T21:00:00+08:00')

    def test_export_allowlist(self):
        data = validate(self.snapshot())
        self.assertEqual(data['summary']['lifetimeTokens'], 1000)
        self.assertEqual(data['daily']['2026-10-25'], 800)
        self.assertNotIn('private@example.invalid', str(data))
        self.assertNotIn('must-not-be-published', str(data))
        data['accountId'] = 'unexpected'
        with self.assertRaises(ValueError):
            validate(data)

    def test_no_invented_zero_for_null_metrics_or_missing_buckets(self):
        response = self.response()
        response['summary']['peakDailyTokens'] = None
        response['dailyUsageBuckets'] = None
        data = validate(sanitize(response, '2026-10-25T21:00:00+08:00'))
        self.assertIsNone(data['daily'])
        root = panel(data, False)
        self.assertIn('N/A', ''.join(root.itertext()))
        self.assertTrue(all('no record' in ''.join(cell.itertext())
                            for cell in root.iter(N+'rect')))

    def test_reject_bad_daily_counts(self):
        for value in (-1, True, 0.1, '100'):
            with self.subTest(value=value):
                response = self.response()
                response['dailyUsageBuckets'][0]['tokens'] = value
                with self.assertRaises(ValueError):
                    sanitize(response, '2026-10-25T21:00:00+08:00')

    def test_reject_duplicates_and_future_days(self):
        for day in ('2026-10-24', '2026-10-26'):
            with self.subTest(day=day):
                response = self.response()
                response['dailyUsageBuckets'].append({'startDate': day, 'tokens': 1})
                with self.assertRaises(ValueError):
                    sanitize(response, '2026-10-25T21:00:00+08:00')

    def test_heatmap_unknown_and_zero_are_distinct(self):
        for dark in (False, True):
            root = panel(self.snapshot(), dark)
            cells = list(root.iter(N+'rect'))
            self.assertEqual(len(cells), 365)
            by_day = {''.join(cell.itertext()).split(':')[0]: cell for cell in cells}
            self.assertNotEqual(by_day['2026-10-23'].get('fill'), by_day['2026-10-24'].get('fill'))
            self.assertIn('no record', ''.join(by_day['2026-10-23'].itertext()))
            self.assertIn('0 tokens', ''.join(by_day['2026-10-24'].itertext()))
            for cell in cells:
                self.assertLessEqual(float(cell.get('x'))+float(cell.get('width')), 872)
            # Lifetime is supplied by the service, never replaced by the daily sum.
            self.assertIn('1.00K', ''.join(root.itertext()))

    def test_heatmap_layout_for_all_weekdays_and_leap_day(self):
        for day in ('2024-02-29', '2026-10-25', '2026-10-26', '2026-10-27',
                    '2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31'):
            response = self.response()
            response['dailyUsageBuckets'] = [{'startDate': day, 'tokens': 800}]
            data = sanitize(response, day+'T21:00:00+08:00')
            root = panel(data, True)
            cells = list(root.iter(N+'rect'))
            self.assertEqual(len(cells), 365)
            self.assertEqual(len({''.join(c.itertext()).split(':')[0] for c in cells}), 365)
            self.assertTrue(all(float(c.get('x'))+12 <= 872 for c in cells))

    def test_reject_unavailable_summary(self):
        for summary in (None, {}, {'lifetimeTokens': -1}):
            with self.assertRaises(ValueError):
                sanitize({'summary': summary, 'dailyUsageBuckets': None}, '2026-10-25T21:00:00+08:00')


if __name__ == '__main__':
    unittest.main()

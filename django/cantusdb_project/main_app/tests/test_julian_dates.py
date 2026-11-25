from django.test import SimpleTestCase

from main_app.julian_dates import DAYS_IN_MONTH, julian_date


class JulianDateTest(SimpleTestCase):
    def test_known_dates(self):
        known = {
            (5, 17): "XVI. Kal. Iun.",  # the example in #2376
            (12, 25): "VIII. Kal. Ian.",
            (1, 1): "Kal. Ian.",
            (1, 6): "VIII. Id. Ian.",
            (2, 2): "IV. Non. Feb.",
            (2, 24): "VI. Kal. Mart.",
            (3, 14): "Pridie Id. Mart.",
            (3, 15): "Id. Mart.",
            (6, 24): "VIII. Kal. Iul.",
            (8, 15): "XVIII. Kal. Sept.",
            (10, 7): "Non. Oct.",
            (1, 14): "XIX. Kal. Feb.",
            (12, 31): "Pridie Kal. Ian.",
        }
        for (month, day), expected in known.items():
            with self.subTest(month=month, day=day):
                self.assertEqual(julian_date(month, day), expected)

    def test_every_day_has_its_own_date(self):
        dates = [
            julian_date(month, day)
            for month in range(1, 13)
            for day in range(1, DAYS_IN_MONTH[month - 1] + 1)
        ]
        self.assertNotIn(None, dates)
        self.assertEqual(len(set(dates)), 365)

    def test_no_date(self):
        for month, day in [
            (None, None),
            (5, None),
            (None, 17),
            (2, 29),
            (4, 31),
            (13, 1),
        ]:
            with self.subTest(month=month, day=day):
                self.assertIsNone(julian_date(month, day))

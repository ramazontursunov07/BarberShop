from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.ai.management.commands.seed_reviews import SAMPLES
from apps.ai.review_insights import MIN_REVIEWS, collect_comments, rating_stats
from apps.shops.models import Shop


class SeedReviewsTests(TestCase):
    def run_cmd(self, name):
        call_command(name, stdout=StringIO())

    def test_requires_seed_demo_first(self):
        with self.assertRaises(CommandError):
            self.run_cmd("seed_reviews")

    def test_creates_reviews_once_and_enough_for_analysis(self):
        self.run_cmd("seed_demo")
        self.run_cmd("seed_reviews")
        shop = Shop.objects.get(name="Demo Barbershop")
        total = rating_stats(shop)["total_reviews"]
        self.assertEqual(total, 2 + len(SAMPLES))
        self.assertGreaterEqual(len(collect_comments(shop)), MIN_REVIEWS)
        self.run_cmd("seed_reviews")  # takroran: dublikat yo'q
        self.assertEqual(rating_stats(shop)["total_reviews"], total)

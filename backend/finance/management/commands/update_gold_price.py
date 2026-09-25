import json
import logging
import os
import time
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from finance.models import GoldPrice, Household

logger = logging.getLogger(__name__)


def fetch_gold_18k_price():
    api_key = os.environ.get("NAVASAN_API_KEY", "").strip()
    if not api_key:
        raise CommandError("Set NAVASAN_API_KEY in your .env file to enable automatic gold prices.")
    url = "http://api.navasan.tech/latest/?" + urlencode({"api_key": api_key, "item": "18ayar"})
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Phinance/1.0"})
    try:
        with urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise CommandError(f"Could not retrieve the Navasan gold price: {exc}") from exc
    try:
        item = data["18ayar"]
        price = int(Decimal(str(item["value"])).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        source_time = datetime.fromtimestamp(int(item["timestamp"]), tz=datetime_timezone.utc)
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise CommandError("Navasan returned an unexpected 18ayar price response.") from exc
    if price <= 0:
        raise CommandError("Navasan returned a non-positive 18ayar price.")
    return price, source_time


def save_price_for_households():
    if not Household.objects.exists():
        return False
    price, source_time = fetch_gold_18k_price()
    for household in Household.objects.iterator():
        GoldPrice.objects.update_or_create(
            household=household,
            defaults={"price_per_gram": price, "source_updated_at": source_time},
        )
    logger.info("Saved latest 18k gold price for household portfolios.")
    return True


class Command(BaseCommand):
    help = "Fetch and save Navasan's 18-karat gold price."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Refresh every 12 hours.")

    def handle(self, *args, **options):
        while True:
            try:
                updated = save_price_for_households()
                if updated:
                    self.stdout.write(self.style.SUCCESS("Gold price updated."))
                    delay = 12 * 60 * 60
                else:
                    logger.info("No household exists yet; checking again in one minute.")
                    delay = 60
            except CommandError as exc:
                if not options["loop"]:
                    raise
                logger.error("Gold price refresh failed: %s", exc)
                delay = 12 * 60 * 60
            if not options["loop"]:
                return
            time.sleep(delay)

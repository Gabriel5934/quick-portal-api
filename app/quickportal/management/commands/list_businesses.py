from django.core.management.base import BaseCommand

from quickportal.models import Business


COLUMNS = (
    ("ID", lambda business: business.id, 2),
    ("TYPE", lambda business: business.type, 5),
    ("PAR", lambda business: business.parent_id or "—", 3),
    ("DT", lambda business: business.document_type, 2),
    ("DOC", lambda business: business.document, 8),
    ("NAME", lambda business: business.name, 12),
    ("TRADE", lambda business: business.trade_name or "—", 6),
    ("CNAE", lambda business: business.cnae.code if business.cnae else "—", 7),
    ("EMAIL", lambda business: business.email, 10),
    ("PHONE", lambda business: business.phone, 8),
    ("LAND", lambda business: business.landline or "—", 4),
    ("STATUS", lambda business: business.status, 6),
)


def truncate(value, max_width):
    text = str(value).replace("\n", " ")
    if len(text) <= max_width:
        return text
    return text[: max_width - 1] + "…"


def render_table(businesses):
    rows = [
        [truncate(accessor(business), max_width) for _, accessor, max_width in COLUMNS]
        for business in businesses
    ]
    headers = [header for header, _, _ in COLUMNS]
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    separator = "+-" + "-+-".join("-" * width for width in widths) + "-+"

    def render_row(values):
        return "| " + " | ".join(
            value.ljust(width) for value, width in zip(values, widths)
        ) + " |"

    lines = [separator, render_row(headers), separator]
    lines.extend(render_row(row) for row in rows)
    lines.append(separator)
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Print all businesses as a formatted table"

    def handle(self, *args, **options):
        businesses = list(
            Business.objects.select_related("parent", "cnae").order_by("id")
        )
        if not businesses:
            self.stdout.write("No businesses found.")
            return

        self.stdout.write(render_table(businesses))
        self.stdout.write(f"{len(businesses)} business(es).")

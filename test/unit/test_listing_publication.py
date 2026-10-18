"""Operational publication must fail closed when listing photos are absent."""

from __future__ import annotations

from datetime import date

import pytest

from app_marketplace import MarketplaceRepo


class Cursor:
    def __init__(self, returned=None):
        self.statements = []
        self.parameters = []
        self.returned = returned

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, parameters):
        self.statements.append(sql)
        self.parameters.append(tuple(parameters))

    def fetchone(self):
        return self.returned


class Connection:
    def __init__(self, result=None):
        self.cur = Cursor(result)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cur


def test_draft_insert_avoids_premature_marketplace_publication():
    connection = Connection()
    repo = MarketplaceRepo(lambda: connection, "shipp")
    listing_id = repo.create_listing(
        donor_id="d1", title="Table", description="Wood table",
        category="FURNITURE", condition="GOOD", location="Abu Dhabi",
        latitude=24.5, longitude=54.4,
        available_until=date(2026, 11, 20),
        initial_status="DRAFT",
    )
    assert listing_id
    assert connection.cur.parameters[-1][-1] == "DRAFT"
    assert "VALUES" in connection.cur.statements[-1]
    assert "INSERT INTO shipp.listings" in connection.cur.statements[-1]


def test_publish_requires_donor_ownership_and_stored_image():
    connection = Connection(("listing-1",))
    repo = MarketplaceRepo(lambda: connection, "shipp")
    repo.publish_listing_with_images(listing_id="listing-1", donor_id="donor-1")
    sql = connection.cur.statements[-1]
    assert "status = 'DRAFT'" in sql
    assert "EXISTS" in sql and "shipp.listing_files" in sql
    assert "file_type LIKE 'image/%%'" in sql
    assert "RETURNING l.listing_id" in sql
    assert connection.cur.parameters[-1] == ("listing-1", "donor-1")


def test_publish_rejected_without_image_or_authorization():
    connection = Connection(None)
    repo = MarketplaceRepo(lambda: connection, "shipp")
    with pytest.raises(RuntimeError, match="not published"):
        repo.publish_listing_with_images(listing_id="listing-1", donor_id="donor-1")
    with pytest.raises(ValueError, match="required"):
        repo.publish_listing_with_images(listing_id="", donor_id="donor-1")


def test_publication_ui_uses_two_phase_write():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] / "ui/pages/donate.py").read_text()
    assert 'initial_status="DRAFT"' in source
    assert "marketplace.save_listing_images(" in source
    assert "marketplace.publish_listing_with_images(" in source
    assert source.index("marketplace.save_listing_images(") < source.index(
        "marketplace.publish_listing_with_images("
    )

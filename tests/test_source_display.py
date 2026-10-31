"""
Sources are shown with a file name only and PDF pages counted from 1.
Stored metadata keeps the full path and the 0-based page.
"""
import pytest

from rag.qa_chain import display_name, display_page, format_sources, public_metadata


@pytest.mark.parametrize("stored,shown", [
    ("/home/someone/project/data/automotive/obd.pdf", "obd.pdf"),
    ("data/automotive/obd.pdf", "obd.pdf"),
    ("C:\\Users\\someone\\data\\catalog.csv", "catalog.csv"),
    ("obd.pdf", "obd.pdf"),
])
def test_display_name_drops_directories(stored, shown):
    assert display_name(stored) == shown


def test_display_page_is_one_based_for_numbers_only():
    assert display_page(0) == 1
    assert display_page(11) == 12
    assert display_page("N/A") == "N/A"


def test_format_sources_hides_the_path_and_counts_pages_from_one():
    metadata = {"source": "/srv/rag/data/automotive/obd.pdf", "source_type": "pdf", "page": 0}
    source = format_sources(["OBD-II text"], [metadata])[0]
    assert source["source"] == "obd.pdf"
    assert source["page"] == 1
    assert metadata["page"] == 0 and metadata["source"].startswith("/srv/")  # input is not modified


def test_format_sources_hides_the_path_for_csv_rows():
    metadata = {"source": "/srv/rag/data/products/catalog.csv", "source_type": "csv", "row_id": "4"}
    source = format_sources(["row"], [metadata])[0]
    assert source["source"] == "catalog.csv"
    assert source["row_id"] == "4"


def test_public_metadata_returns_a_copy():
    metadata = {"source": "/a/b/c.pdf", "page": 2, "domain": "x"}
    shown = public_metadata(metadata)
    assert shown == {"source": "c.pdf", "page": 3, "domain": "x"}
    assert metadata["page"] == 2

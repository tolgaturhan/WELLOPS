from __future__ import annotations
from typing import List, Dict, Any


def mock_well_tree() -> List[Dict[str, Any]]:
    """
    Mock tree structure.
    Later this will be replaced by DB-backed loader.
    """
    return [
        {
            "key": "wellops.header",
            "title": "Overview",
            "type": "GROUP",
            "children": [
                {
                    "key": "wellops.well_identity",
                    "title": "Well Identity",
                    "type": "SECTION",
                    "selected": True,
                }
            ],
        },
        {
            "key": "wellops.planning",
            "title": "Planning",
            "type": "GROUP",
            "children": [
                {
                    "key": "wellops.drilling_program",
                    "title": "Drilling Program",
                    "type": "SECTION",
                    "selected": True,
                },
                {
                    "key": "wellops.hse",
                    "title": "HSE",
                    "type": "SECTION",
                    "selected": False,
                },
            ],
        },
    ]
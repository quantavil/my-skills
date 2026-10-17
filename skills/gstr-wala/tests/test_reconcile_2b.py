"""Pytest test suite for reconcile_2b.py."""

import pytest
from scripts.reconcile_2b import normalize_inum, reconcile


def test_normalize_invoice_number():
    assert normalize_inum("INV/2026/001") == "INV2026001"
    assert normalize_inum("inv-0042") == "INV42"
    assert normalize_inum("000123") == "123"
    assert normalize_inum("GST-INV#99") == "GSTINV99"


def test_full_reconciliation_cycle():
    pr_invoices = [
        {"ctin": "29BBBBB1111B1Z2", "inum": "INV/2026/101", "txval": 10000.0, "iamt": 1800.0},
        {"ctin": "29BBBBB1111B1Z2", "inum": "INV-102", "txval": 5000.0, "iamt": 900.50},
        {"ctin": "29CCCCC2222C1Z3", "inum": "INV-103", "txval": 20000.0, "iamt": 3600.0, "is_blocked_17_5": True},
        {"ctin": "29DDDDD3333D1Z4", "inum": "INV-104", "txval": 10000.0, "iamt": 1800.0, "unpaid_days": 200},
        {"ctin": "29EEEEE4444E1Z5", "inum": "INV-105", "txval": 50000.0, "iamt": 9000.0},
        {"ctin": "29FFFFF5555F1Z6", "inum": "INV-106", "txval": 10000.0, "iamt": 1800.0}
    ]

    g2b_raw = {
        "data": {
            "docdata": {
                "b2b": [
                    {
                        "ctin": "29BBBBB1111B1Z2",
                        "inv": [
                            {"inum": "INV-2026-101", "dt": "10-04-2026", "itcavl": "Y", "items": [{"txval": 10000.0, "iamt": 1800.0}]},
                            {"inum": "000102", "dt": "12-04-2026", "itcavl": "Y", "items": [{"txval": 5000.0, "iamt": 900.0}]}
                        ]
                    },
                    {
                        "ctin": "29CCCCC2222C1Z3",
                        "inv": [
                            {"inum": "INV-103", "dt": "15-04-2026", "itcavl": "Y", "items": [{"txval": 20000.0, "iamt": 3600.0}]}
                        ]
                    },
                    {
                        "ctin": "29DDDDD3333D1Z4",
                        "inv": [
                            {"inum": "INV-104", "dt": "15-04-2026", "itcavl": "Y", "items": [{"txval": 10000.0, "iamt": 1800.0}]}
                        ]
                    },
                    {
                        "ctin": "29FFFFF5555F1Z6",
                        "inv": [
                            {"inum": "INV-106", "dt": "15-04-2026", "itcavl": "N", "rsn": "POS Mismatch", "items": [{"txval": 10000.0, "iamt": 1800.0}]}
                        ]
                    },
                    {
                        "ctin": "29GGGGG6666G1Z7",
                        "inv": [
                            {"inum": "INV-999", "dt": "18-04-2026", "itcavl": "Y", "items": [{"txval": 15000.0, "iamt": 2700.0}]}
                        ]
                    }
                ]
            }
        }
    }

    res = reconcile(pr_invoices, g2b_raw)
    s = res["summary"]
    t4 = res["gstr3b_table_4_auto_population"]

    assert s["exact_matched_count"] == 1
    assert s["tolerance_matched_count"] == 1
    assert s["blocked_17_5_count"] == 1
    assert s["rule_37_count"] == 1
    assert s["in_books_only_count"] == 1
    assert s["in_2b_only_count"] == 1
    assert s["ineligible_2b_count"] == 1

    # Matched ITC in Table 4(A)(5) = 1800 (INV-101) + 900 (INV-102) = 2700
    assert t4["table_4_a_5_all_other_itc"]["iamt"] == 2700.0

    # Permanent reversal 4(B)(1) = 3600 (INV-103)
    assert t4["table_4_b_1_permanent_reversals_17_5"]["iamt"] == 3600.0

    # Temporary reversal 4(B)(2) = 1800 (INV-104)
    assert t4["table_4_b_2_temporary_reversals_rule37"]["iamt"] == 1800.0

    # Ineligible 4(D)(2) = 1800 (INV-106)
    assert t4["table_4_d_2_ineligible_16_4"]["iamt"] == 1800.0

    # Deferred ITC = 9000 (INV-105)
    assert t4["deferred_itc_missing_in_2b"]["iamt"] == 9000.0

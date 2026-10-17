"""Pytest test suite for GSTR-1 & GSTR-3B JSON generators and Bridge."""

import json
import pytest
from scripts.generate_gstr1_json import generate_portal_gstr1
from scripts.generate_gstr3b_json import generate_portal_gstr3b
from scripts.gstr1_to_3b_bridge import bridge_gstr1_and_2b_to_3b, check_drc_mismatch_risks


def test_generate_gstr1_portal_schema():
    data = {
        "gstin": "27AAAAA0000A1Z2",
        "fp": "042026",
        "gt": 10000000.0,
        "cur_gt": 2500000.0,
        "invoices": [
            {
                "inum": "INV-001",
                "idt": "10-04-2026",
                "pos": "29",
                "ctin": "29BBBBB1111B1Z2",
                "val": 118000.0,
                "items": [{"txval": 100000.0, "rt": 18.0, "iamt": 18000.0, "hsn_sc": "8471", "uqc": "NOS", "qty": 10}]
            },
            {
                "inum": "INV-002",
                "idt": "12-04-2026",
                "pos": "29",
                "val": 177000.0,
                "items": [{"txval": 150000.0, "rt": 18.0, "iamt": 27000.0, "hsn_sc": "8471", "uqc": "NOS", "qty": 15}]
            }
        ]
    }

    portal_json = generate_portal_gstr1(data)
    assert portal_json["gstin"] == "27AAAAA0000A1Z2"
    assert portal_json["fp"] == "042026"
    assert len(portal_json["b2b"]) == 1
    assert len(portal_json["b2cl"]) == 1
    assert len(portal_json["hsn"]["data"]) == 2


def test_generate_gstr3b_portal_schema():
    data = {
        "gstin": "27AAAAA0000A1Z2",
        "ret_period": "042026",
        "outward_supplies": {
            "taxable": {
                "txval": 250000.0,
                "iamt": 45000.0,
                "camt": 0.0,
                "samt": 0.0,
                "csamt": 0.0
            }
        },
        "itc": {
            "available": {
                "all_other": {
                    "iamt": 30000.0,
                    "camt": 0.0,
                    "samt": 0.0,
                    "csamt": 0.0
                }
            }
        }
    }

    portal_json = generate_portal_gstr3b(data)
    assert portal_json["gstin"] == "27AAAAA0000A1Z2"
    assert portal_json["ret_period"] == "042026"
    assert portal_json["sup_details"]["osup_det"]["txval"] == 250000.0
    assert portal_json["sup_details"]["osup_det"]["iamt"] == 45000.0
    # ITC offset 30,000 against 45,000 -> 15,000 paid in cash
    assert portal_json["tx_pmt"]["tx_py"][0]["paid_itc"]["iamt"] == 30000.0
    assert portal_json["tx_pmt"]["tx_py"][0]["paid_cash"]["iamt"] == 15000.0


def test_bridge_and_drc_checks():
    g1_data = {
        "gstin": "27AAAAA0000A1Z2",
        "fp": "042026",
        "invoices": [
            {
                "inum": "INV-001",
                "idt": "10-04-2026",
                "pos": "27",
                "items": [{"txval": 100000.0, "rt": 18.0, "camt": 9000.0, "samt": 9000.0}]
            }
        ]
    }

    recon_data = {
        "gstr3b_table_4_auto_population": {
            "table_4_a_5_all_other_itc": {"iamt": 5000.0, "camt": 2000.0, "samt": 2000.0, "csamt": 0.0},
            "table_4_b_1_permanent_reversals_17_5": {"iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
            "table_4_b_2_temporary_reversals_rule37": {"iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
            "table_4_d_2_ineligible_16_4": {"iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0}
        }
    }

    g3b_input = bridge_gstr1_and_2b_to_3b(g1_data, recon_data)
    assert g3b_input["outward_supplies"]["taxable"]["camt"] == 9000.0
    assert g3b_input["outward_supplies"]["taxable"]["samt"] == 9000.0
    assert g3b_input["itc"]["available"]["all_other"]["iamt"] == 5000.0

    drc_res = check_drc_mismatch_risks(
        gstr1_summary={"total_tax": 18000.0},
        gstr3b_data=g3b_input,
        gstr2b_total_itc=9000.0
    )
    assert drc_res["drc_01b_liability_mismatch"]["risk_flag"] is False
    assert drc_res["drc_01c_itc_mismatch"]["risk_flag"] is False

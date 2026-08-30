"""Run all project scrapers."""

from __future__ import annotations

from typing import Any

from scrapers import bbtender, bdtender_financial_service, petrobangla, tenderbazar


def run_all() -> dict[str, Any]:
    """Run every scraper using its own defaults and notification handling."""
    print("Running Bangladesh Bank tender sync...")
    bangladesh_bank = bbtender.run()
    print(
        f"Bangladesh Bank sync status: updated={bangladesh_bank['updated']}, "
        f"new={bangladesh_bank['new_count']}"
    )

    print("Running BDTender financial service sync...")
    financial_service = bdtender_financial_service.run()
    print(
        f"BDTender financial service sync status: updated={financial_service['updated']}, "
        f"new={financial_service['new_count']}"
    )

    print("Running Petrobangla sync...")
    petrobangla_sync = petrobangla.run()
    print(
        f"Petrobangla sync status: updated={petrobangla_sync['updated']}, "
        f"new={petrobangla_sync['new_count']}"
    )

    print("Running TenderBazar sync...")
    tender_bazar = tenderbazar.run()

    return {
        "bbtender": bangladesh_bank,
        "bdtender_financial_service": financial_service,
        "petrobangla": petrobangla_sync,
        "tenderbazar": tender_bazar,
    }
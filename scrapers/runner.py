"""Run all project scrapers."""

from __future__ import annotations

from typing import Any

from scrapers import BGDCL, GTCL, PGCL, bbtender, bdtender_financial_service, eprocure, jalalabad_gas, lp_gas, meghna_petrolium, padma_oil, jamuna_oil, eastern_refinery, petrobangla, tenderbazar


def run_all() -> dict[str, Any]:
    """Run every scraper using its own defaults and notification handling."""

    def safe_run(name: str, func):
        try:
            print(f"Running {name} sync...")
            result = func()
            print(
                f"{name} sync status: updated={result.get('updated', False)}, "
                f"new={result.get('new_count', 0)}"
            )
            return result
        except Exception as exc:
            print(f"{name} sync failed: {exc}")
            return {
                "updated": False,
                "saved_path": "",
                "total_loaded": 0,
                "new_count": 0,
                "new_tenders": [],
                "error": str(exc),
            }

    bangladesh_bank = safe_run("Bangladesh Bank", bbtender.run)
    financial_service = safe_run("BDTender financial service", bdtender_financial_service.run)
    eprocure_sync = safe_run("eProcure", eprocure.run)
    petrobangla_sync = safe_run("Petrobangla", petrobangla.run)
    gtcl_sync = safe_run("GTCL", GTCL.run)
    padma_oil_sync = safe_run("Padma Oil", padma_oil.run)
    jamuna_oil_sync = safe_run("Jamuna Oil", jamuna_oil.run)
    meghna_petrolium_sync = safe_run("Meghna Petrolium", meghna_petrolium.run)
    eastern_refinery_sync = safe_run("Eastern Refinery", eastern_refinery.run)
    lp_gas_sync = safe_run("LP Gas", lp_gas.run)
    bgdcl_sync = safe_run("BGDCL", BGDCL.run)
    jalalabad_gas_sync = safe_run("Jalalabad Gas", jalalabad_gas.run)
    pgcl_sync = safe_run("PGCL", PGCL.run)
    tender_bazar = safe_run("TenderBazar", tenderbazar.run)

    return {
        "bbtender": bangladesh_bank,
        "bdtender_financial_service": financial_service,
        "eprocure": eprocure_sync,
        "petrobangla": petrobangla_sync,
        "gtcl": gtcl_sync,
        "padma_oil": padma_oil_sync,
        "meghna_petrolium": meghna_petrolium_sync,
        "jamuna_oil": jamuna_oil_sync,
        "eastern_refinery": eastern_refinery_sync,
        "lp_gas": lp_gas_sync,
        "bgdcl": bgdcl_sync,
        "jalalabad_gas": jalalabad_gas_sync,
        "pgcl": pgcl_sync,
        "tenderbazar": tender_bazar,
    }
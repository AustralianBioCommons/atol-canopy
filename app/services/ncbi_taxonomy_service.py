import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# Adapted from:
# - /Users/emilylm/Repositories/biocommons/tutorial-fetch-ncbi-data/src/taxonomy_fetcher.py
# - /Users/emilylm/Repositories/biocommons/tutorial-fetch-ncbi-data/src/parent_lineage_enrichment.py
related_mitos: dict[int | str, str] = {}
no_mitos: set[int | str] = set()

# Cap concurrent in-flight NCBI HTTP requests to avoid rate-limiting
_ncbi_semaphore = threading.Semaphore(10)


def normalize_tax_id(value: int | str | None) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    stripped = str(value).strip()
    if stripped.isdigit():
        return int(stripped)
    return stripped


def chunked(items: list[int | str], size: int) -> list[list[int | str]]:
    if size <= 0:
        raise ValueError("size must be > 0")
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_taxonomy_url(tax_ids: list[int | str], endpoint: str) -> str:
    taxons = ",".join(str(tax_id) for tax_id in tax_ids)
    if endpoint == "taxonomy":
        return f"https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{taxons}/dataset_report"
    if endpoint == "organelle":
        return f"https://api.ncbi.nlm.nih.gov/datasets/v2/organelle/taxon/{taxons}/dataset_report"
    raise ValueError(f"Unsupported endpoint: {endpoint}")


def fetch_reports(
    tax_ids: list[int | str],
    endpoint: str,
    *,
    max_retries: int = 3,
    backoff_seconds: int = 1,
    timeout_seconds: int = 20,
    sleep_fn=time.sleep,
) -> list[dict[str, Any]]:
    """Fetch taxonomy report dicts for a batch of tax_ids."""
    url = build_taxonomy_url(tax_ids, endpoint)
    logger.info("Fetching NCBI %s reports for tax_ids=%s", endpoint, tax_ids)

    for attempt in range(1, max_retries + 1):
        try:
            with _ncbi_semaphore:
                response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            reports = payload.get("reports", [])
            logger.info(
                "Fetched %s NCBI %s reports for tax_ids=%s",
                len(reports),
                endpoint,
                tax_ids,
            )
            return reports
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            logger.warning(
                "NCBI %s fetch failed for tax_ids=%s (attempt %s/%s): %s",
                endpoint,
                tax_ids,
                attempt,
                max_retries,
                exc,
            )
            if attempt == max_retries:
                raise RuntimeError(
                    f"Unable to fetch {endpoint} reports for tax_ids {tax_ids} after {max_retries} attempts"
                ) from exc
            sleep_fn(backoff_seconds * (2 ** (attempt - 1)))

    raise RuntimeError("Unexpected retry loop exit")


def build_lineage(
    classification: dict[str, Any],
    *,
    current_rank: str | None,
    current_name: str | None,
) -> list[dict[str, str]]:
    lineage: list[dict[str, str]] = []

    if isinstance(classification, dict):
        domain_name = (classification.get("domain") or {}).get("name")
        if domain_name:
            lineage.append({"rank": "domain", "name": domain_name})
        for rank, node in classification.items():
            if not isinstance(node, dict):
                continue
            if rank == "domain":
                continue
            name = node.get("name")
            if not name:
                continue
            lineage.append({"rank": str(rank), "name": name})

    if current_name:
        current_rank_label = str(current_rank).lower() if current_rank else "current"
        if not lineage or lineage[-1]["name"] != current_name:
            lineage.append({"rank": current_rank_label, "name": current_name})

    return lineage


def lineage_to_string(lineage: list[dict[str, str]]) -> str | None:
    names = [item.get("name") for item in lineage if item.get("name")]
    return "; ".join(names) if names else None


def get_report_query_taxid(report: dict[str, Any]) -> int | str | None:
    query = report.get("query") or []
    if not query:
        return None
    return normalize_tax_id(query[0])


def prepare_unique_taxa(
    input_taxa: list[dict[str, Any]],
) -> tuple[list[int | str], dict[int | str, str | None], list[dict[str, Any]]]:
    unique_taxids: list[int | str] = []
    raw_name_by_taxid: dict[int | str, str | None] = {}
    pre_collected_unmapped: list[dict[str, Any]] = []
    seen_taxids: set[int | str] = set()

    for item in input_taxa:
        tax_id = normalize_tax_id(item.get("tax_id"))
        raw_name = item.get("scientific_name")

        if tax_id is None:
            logger.error("Skipping record with missing tax_id (scientific_name=%s)", raw_name)
            pre_collected_unmapped.append(
                {"taxon_id": None, "raw_scientific_name": raw_name, "error": "missing_tax_id"}
            )
            continue

        if tax_id in seen_taxids:
            logger.debug("Skipping duplicate tax_id %s", tax_id)
            continue

        seen_taxids.add(tax_id)
        unique_taxids.append(tax_id)
        raw_name_by_taxid[tax_id] = raw_name

    return unique_taxids, raw_name_by_taxid, pre_collected_unmapped


def has_useful_taxonomy_data(extracted: dict[str, Any]) -> bool:
    return any(value is not None for value in extracted.values())


def prepare_unique_parents(input_parents: list[int] | None) -> list[int | str]:
    unique_taxids: list[int | str] = []
    seen_taxids: set[int | str] = set()

    for taxid in input_parents or []:
        if taxid is None or taxid in seen_taxids:
            continue
        seen_taxids.add(taxid)
        unique_taxids.append(taxid)

    return unique_taxids


def extract_sci_name(report: dict[str, Any]) -> dict[int, str]:
    taxonomy = report.get("taxonomy") or {}
    tax_id = taxonomy.get("tax_id")
    sci_name = (taxonomy.get("current_scientific_name") or {}).get("name")
    return {tax_id: sci_name}


def process_parent_batch(
    taxon_batch: list[int | str],
) -> tuple[dict[int, str], list[dict[str, Any]]]:
    mapped_batch: dict[int, str] = {}
    unmapped_batch: list[dict[str, Any]] = []

    logger.info("Processing NCBI parent batch of %s tax_ids", len(taxon_batch))
    try:
        reports = fetch_reports(taxon_batch, endpoint="taxonomy")
    except RuntimeError as exc:
        logger.error("NCBI parent batch fetch failed for tax_ids=%s: %s", taxon_batch, exc)
        for tax_id in taxon_batch:
            unmapped_batch.append({"taxon_id": tax_id, "error": str(exc)})
        return mapped_batch, unmapped_batch

    received_query_taxids: set[int | str] = set()
    for report in reports:
        query_taxid = get_report_query_taxid(report)
        if query_taxid is not None:
            received_query_taxids.add(query_taxid)

        sci_name = extract_sci_name(report)
        if not sci_name:
            unmapped_batch.append(
                {"taxon_id": query_taxid, "error": "unexpected response structure"}
            )
            continue
        mapped_batch.update(sci_name)

    missing_taxids = [tax_id for tax_id in taxon_batch if tax_id not in received_query_taxids]
    for tax_id in missing_taxids:
        unmapped_batch.append({"taxon_id": tax_id, "error": "no report returned"})

    return mapped_batch, unmapped_batch


def process_parents(parent_taxids: list[int] | None) -> str | None:
    unique_parents = prepare_unique_parents(parent_taxids)
    if not unique_parents:
        return None

    mapped_parents, unmapped_parents = process_parent_batch(unique_parents)
    ordered_parents: list[str] = []
    for parent in unique_parents:
        if parent in {1, 131567}:
            continue
        ordered_parent = mapped_parents.get(parent)
        if ordered_parent:
            ordered_parents.append(ordered_parent)

    logger.debug("Mapped parents=%s unmapped=%s", mapped_parents, unmapped_parents)
    return "; ".join(ordered_parents) if ordered_parents else None


def get_taxon_w_org(
    reports: list[dict[str, Any]],
    organelle_type: str,
    taxid: int | str,
) -> str | None:
    for report in reports:
        if report.get("description") != organelle_type:
            continue
        organism_info = report.get("organism") or {}
        scientific_name = organism_info.get("organism_name")
        if organelle_type == "Mitochondrion" and scientific_name:
            related_mitos[taxid] = scientific_name
        return scientific_name
    return None


def organelle_ref_lookup(
    taxid_lineage: list[int] | None,
    species_taxid: int | None,
    organelle_type: str,
) -> str | None:
    if species_taxid is None:
        return None

    rev_order_lineage = list((taxid_lineage or [])[::-1])
    rev_order_lineage.insert(0, species_taxid)

    for taxid in rev_order_lineage:
        if organelle_type == "Mitochondrion" and taxid in related_mitos:
            return related_mitos.get(taxid)
        if organelle_type == "Mitochondrion" and taxid in no_mitos:
            continue

        try:
            reports = fetch_reports([taxid], endpoint="organelle")
        except RuntimeError as exc:
            logger.error("Organelle fetch failed for tax_id=%s: %s", taxid, exc)
            continue

        if not reports:
            no_mitos.add(taxid)
            continue

        taxon_check = get_taxon_w_org(reports, organelle_type, taxid)
        if taxon_check is not None:
            return taxon_check

    return None


def extract_taxonomy_fields(report: dict[str, Any]) -> dict[str, Any]:
    taxonomy = report.get("taxonomy") or {}
    classification = taxonomy.get("classification") or {}
    current_rank = taxonomy.get("rank")
    current_name = (taxonomy.get("current_scientific_name") or {}).get("name")
    lineage = build_lineage(classification, current_rank=current_rank, current_name=current_name)

    parents = taxonomy.get("parents")
    species_taxid = taxonomy.get("tax_id")

    with ThreadPoolExecutor(max_workers=2) as executor:
        full_lineage_future = executor.submit(process_parents, parents)
        mito_future = executor.submit(organelle_ref_lookup, parents, species_taxid, "Mitochondrion")
        ncbi_full_lineage = full_lineage_future.result()
        mitohifi_reference_species = mito_future.result()

    return {
        "taxon_id": species_taxid,
        "ncbi_taxon_id": species_taxid,
        "ncbi_rank": current_rank,
        "ncbi_scientific_name": current_name,
        "ncbi_authority": (taxonomy.get("current_scientific_name") or {}).get("authority"),
        "ncbi_common_name": taxonomy.get("curator_common_name"),
        "ncbi_class": (classification.get("class") or {}).get("name"),
        "ncbi_order": (classification.get("order") or {}).get("name"),
        "ncbi_family": (classification.get("family") or {}).get("name"),
        "ncbi_lineage": lineage,
        "ncbi_tax_string": lineage_to_string(lineage),
        "ncbi_full_lineage": ncbi_full_lineage,
        "mitohifi_reference_species": mitohifi_reference_species,
    }


def process_batch(
    taxon_batch: list[int | str],
    raw_name_by_taxid: dict[int | str, str | None],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapped_batch: list[dict[str, Any]] = []
    unmapped_batch: list[dict[str, Any]] = []

    logger.info("Processing NCBI taxonomy batch of %s tax_ids", len(taxon_batch))
    try:
        reports = fetch_reports(taxon_batch, endpoint="taxonomy")
    except RuntimeError as exc:
        logger.error("NCBI taxonomy batch fetch failed for tax_ids=%s: %s", taxon_batch, exc)
        for tax_id in taxon_batch:
            unmapped_batch.append(
                {
                    "taxon_id": tax_id,
                    "raw_scientific_name": raw_name_by_taxid.get(tax_id),
                    "error": str(exc),
                }
            )
        return mapped_batch, unmapped_batch

    received_query_taxids: set[int | str] = set()
    report_query_pairs: list[tuple[dict[str, Any], int | str | None]] = []
    for report in reports:
        query_taxid = get_report_query_taxid(report)
        if query_taxid is not None:
            received_query_taxids.add(query_taxid)
        report_query_pairs.append((report, query_taxid))

    with ThreadPoolExecutor(max_workers=len(report_query_pairs) or 1) as executor:
        future_to_pair = {
            executor.submit(extract_taxonomy_fields, report): (report, query_taxid)
            for report, query_taxid in report_query_pairs
        }
        for future in as_completed(future_to_pair):
            report, query_taxid = future_to_pair[future]
            try:
                extracted = future.result()
            except Exception as exc:
                unmapped_batch.append(
                    {
                        "taxon_id": query_taxid,
                        "raw_scientific_name": raw_name_by_taxid.get(query_taxid),
                        "error": str(exc),
                    }
                )
                continue

            if not has_useful_taxonomy_data(extracted):
                unmapped_batch.append(
                    {
                        "taxon_id": query_taxid,
                        "raw_scientific_name": raw_name_by_taxid.get(query_taxid),
                        "error": "unexpected response structure",
                    }
                )
                continue

            if extracted.get("taxon_id") is not None:
                extracted["supplied_taxon_id"] = query_taxid
                extracted["supplied_name"] = raw_name_by_taxid.get(query_taxid)
                mapped_batch.append(extracted)
                logger.info("Mapped NCBI taxonomy for requested taxon_id=%s", query_taxid)
                continue

            error_reason = (((report.get("errors") or [{}])[0]).get("reason")) or "missing taxonomy"
            unmapped_batch.append(
                {
                    "taxon_id": query_taxid,
                    "raw_scientific_name": raw_name_by_taxid.get(query_taxid),
                    "error": error_reason,
                }
            )

    missing_taxids = [tax_id for tax_id in taxon_batch if tax_id not in received_query_taxids]
    for tax_id in missing_taxids:
        unmapped_batch.append(
            {
                "taxon_id": tax_id,
                "raw_scientific_name": raw_name_by_taxid.get(tax_id),
                "error": "no report returned",
            }
        )

    return mapped_batch, unmapped_batch


def process_taxa(
    input_taxa: list[dict[str, Any]],
    *,
    batch_size: int = 20,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapped: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []

    logger.info("Starting NCBI taxonomy processing for %s input records", len(input_taxa))
    unique_taxids, raw_name_by_taxid, pre_collected_unmapped = prepare_unique_taxa(input_taxa)
    unmapped.extend(pre_collected_unmapped)
    logger.info(
        "Prepared %s unique tax_ids for NCBI processing (%s pre-marked unmapped)",
        len(unique_taxids),
        len(pre_collected_unmapped),
    )

    batches = chunked(unique_taxids, batch_size)
    with ThreadPoolExecutor(max_workers=len(batches) or 1) as executor:
        futures = [executor.submit(process_batch, batch, raw_name_by_taxid) for batch in batches]
        for future in as_completed(futures):
            mapped_batch, unmapped_batch = future.result()
            mapped.extend(mapped_batch)
            unmapped.extend(unmapped_batch)

    logger.info("Finished NCBI processing: %s mapped, %s unmapped", len(mapped), len(unmapped))
    return mapped, unmapped


def fetch_taxonomy_for_taxon_ids(
    taxa: dict[int, Optional[str]],
    *,
    batch_size: int = 20,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    input_taxa = [
        {"tax_id": taxon_id, "scientific_name": scientific_name}
        for taxon_id, scientific_name in taxa.items()
    ]
    mapped, unmapped = process_taxa(input_taxa, batch_size=batch_size)
    mapped_by_taxon_id = {
        int(item["taxon_id"]): item for item in mapped if item.get("taxon_id") is not None
    }
    return mapped_by_taxon_id, unmapped

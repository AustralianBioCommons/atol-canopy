import logging
import time

import requests

logger = logging.getLogger(__name__)


class NcbiTaxonomyService:
    related_mitos = {}
    no_mitos = []

    def configure_logging() -> None:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

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
        return [items[i : i + size] for i in range(0, len(items), size)]

    def build_taxonomy_url(tax_ids: list[int | str], endpoint: str) -> str:
        taxons = ",".join(str(tax_id) for tax_id in tax_ids)
        if endpoint == "taxonomy":
            return (
                "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/"
                f"taxon/{taxons}/dataset_report"
            )
        elif endpoint == "organelle":
            return (
                "https://api.ncbi.nlm.nih.gov/datasets/v2/organelle/"
                f"taxon/{taxons}/dataset_report"
            )

    def fetch_reports(
        tax_ids: list[int | str],
        endpoint: str,
        *,
        max_retries: int = 3,
        backoff_seconds: int = 1,
        timeout_seconds: int = 20,
        sleep_fn=time.sleep,
    ) -> list[dict]:
        """Fetch taxonomy report dicts for a batch of tax_ids.

        Raises RuntimeError if request fails after retries.
        """
        url = build_taxonomy_url(tax_ids, endpoint)

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, timeout=timeout_seconds)
                response.raise_for_status()
                payload = response.json()
                reports = payload.get("reports", [])
                return reports
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                logger.warning(
                    "Bulk fetch failed for tax_ids %s (attempt %s/%s): %s",
                    tax_ids,
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt == max_retries:
                    raise RuntimeError(
                        "Unable to fetch taxonomy for tax_ids "
                        f"{tax_ids} after {max_retries} attempts"
                    ) from exc
                sleep_fn(backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("Unexpected retry loop exit")

    def extract_taxonomy_fields(report: dict) -> dict:
        """Extract required taxonomy fields from an NCBI report object."""
        taxonomy = report.get("taxonomy") or {}
        classification = taxonomy.get("classification") or {}
        current_rank = taxonomy.get("rank")
        current_name = (taxonomy.get("current_scientific_name") or {}).get("name")
        lineage = build_lineage(
            classification, current_rank=current_rank, current_name=current_name
        )

        return {
            "taxon_id": taxonomy.get("tax_id"),
            "ncbi_rank": current_rank,
            "ncbi_scientific_name": current_name,
            "ncbi_authority": (taxonomy.get("current_scientific_name") or {}).get("authority"),
            "ncbi_common_name": taxonomy.get("curator_common_name"),
            "ncbi_class": (classification.get("class") or {}).get("name"),
            "ncbi_order": (classification.get("order") or {}).get("name"),
            "ncbi_family": (classification.get("family") or {}).get("name"),
            "ncbi_lineage": lineage,
            "ncbi_tax_string": lineage_to_string(lineage),
            "ncbi_full_lineage": process_parents(taxonomy.get("parents")),
            "mito_ref": organelle_ref_lookup(
                taxonomy.get("parents"), taxonomy.get("tax_id"), organelle_type="Mitochondrion"
            ),
        }

    def has_useful_taxonomy_data(extracted: dict) -> bool:
        """Return True if at least one expected extracted value is present."""
        return any(value is not None for value in extracted.values())

    def build_lineage(
        classification: dict,
        *,
        current_rank: str | None,
        current_name: str | None,
    ) -> list[dict]:
        """Build ordered lineage as rank/name objects.

        We keep API-provided classification order, which is largest -> smallest in NCBI payloads.
        """
        lineage: list[dict] = []

        if isinstance(classification, dict):
            domain_name = classification.get("domain", {}).get("name")
            if domain_name:
                lineage.append({"rank": "domain", "name": domain_name})
            for rank, node in classification.items():
                if not isinstance(node, dict):
                    continue
                name = node.get("name")
                if not name:
                    continue
                if rank == "domain":
                    continue
                lineage.append({"rank": str(rank), "name": name})

        if current_name:
            current_rank_label = str(current_rank).lower() if current_rank else "current"
            if not lineage or lineage[-1]["name"] != current_name:
                lineage.append({"rank": current_rank_label, "name": current_name})

        return lineage

    def lineage_to_string(lineage: list[dict]) -> str | None:
        names = [item.get("name") for item in lineage if item.get("name")]
        return "; ".join(names) if names else None

    def get_report_query_taxid(report: dict) -> int | str | None:
        query = report.get("query") or []
        if not query:
            return None
        return normalize_tax_id(query[0])

    def prepare_unique_taxa(
        input_taxa: list[dict],
    ) -> tuple[list[int | str], dict[int | str, str | None], list[dict]]:
        """Return (unique_taxids, raw_name_by_taxid, pre_collected_unmapped)."""
        unique_taxids: list[int | str] = []
        raw_name_by_taxid: dict[int | str, str | None] = {}
        pre_collected_unmapped: list[dict] = []
        seen_taxids: set[int | str] = set()

        # First pass: normalize IDs, record missing IDs, and preserve input order for unique IDs.
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

    def process_batch(
        taxon_batch: list[int | str],
        raw_name_by_taxid: dict[int | str, str | None],
    ) -> tuple[list[dict], list[dict]]:
        mapped_batch: list[dict] = []
        unmapped_batch: list[dict] = []

        # Batch fetch: if this fails, mark all IDs in the batch as unmapped.
        logger.info("Processing batch of %s tax_ids", len(taxon_batch))
        logger.debug("Batch tax_ids: %s", taxon_batch)
        try:
            reports = fetch_reports(taxon_batch, endpoint="taxonomy")
        except RuntimeError as exc:
            logger.error("Batch fetch failed for tax_ids %s: %s", taxon_batch, exc)
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
        for report in reports:
            query_taxid = get_report_query_taxid(report)
            if query_taxid is not None:
                received_query_taxids.add(query_taxid)

            extracted = extract_taxonomy_fields(report)  # query taxid
            if not has_useful_taxonomy_data(extracted):
                logger.error("Unexpected response structure for tax_id %s", query_taxid)
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
                logger.debug("Mapped tax_id %s", extracted.get("taxon_id"))
                mapped_batch.append(extracted)
                continue

            error_reason = (((report.get("errors") or [{}])[0]).get("reason")) or "missing taxonomy"
            logger.warning("Tax_id %s returned error payload: %s", query_taxid, error_reason)
            unmapped_batch.append(
                {
                    "taxon_id": query_taxid,
                    "raw_scientific_name": raw_name_by_taxid.get(query_taxid),
                    "error": error_reason,
                }
            )

        # If API did not return a report for a requested ID, mark it explicitly.
        missing_taxids = [tax_id for tax_id in taxon_batch if tax_id not in received_query_taxids]
        for tax_id in missing_taxids:
            logger.warning("No report returned for requested tax_id %s", tax_id)
            unmapped_batch.append(
                {
                    "taxon_id": tax_id,
                    "raw_scientific_name": raw_name_by_taxid.get(tax_id),
                    "error": "no report returned",
                }
            )

        return mapped_batch, unmapped_batch

    def process_taxa(
        input_taxa: list[dict], *, batch_size: int = 20
    ) -> tuple[list[dict], list[dict]]:
        """Return (mapped_taxa, unmapped_taxa)."""
        mapped: list[dict] = []
        unmapped: list[dict] = []

        logger.info("Starting taxonomy processing for %s input records", len(input_taxa))
        unique_taxids, raw_name_by_taxid, pre_collected_unmapped = prepare_unique_taxa(input_taxa)
        unmapped.extend(pre_collected_unmapped)
        logger.info(
            "Prepared %s unique tax_ids (%s records pre-marked unmapped)",
            len(unique_taxids),
            len(pre_collected_unmapped),
        )

        # Second pass: fetch and process in bulk batches.
        for taxon_batch in chunked(unique_taxids, batch_size):
            mapped_batch, unmapped_batch = process_batch(taxon_batch, raw_name_by_taxid)
            mapped.extend(mapped_batch)
            unmapped.extend(unmapped_batch)

        logger.info("Finished processing: %s mapped, %s unmapped", len(mapped), len(unmapped))
        return mapped, unmapped

    def prepare_unique_parents(
        input_parents: list[int],
    ) -> list[int | str]:
        """Return (unique_parent_taxids)."""
        unique_taxids: list[int | str] = []
        seen_taxids: set[int | str] = set()

        # First pass: preserve input order for unique IDs.
        for taxid in input_parents:
            if taxid is None:
                logger.error("Skipping record with missing tax_id %s", taxid)
                continue

            if taxid in seen_taxids:
                logger.debug("Skipping duplicate tax_id %s", taxid)
                continue

            seen_taxids.add(taxid)
            unique_taxids.append(taxid)

        return unique_taxids

    def process_parent_batch(
        taxon_batch: list[int | str],
    ) -> tuple[list[dict], list[dict]]:
        mapped_batch: dict[int:str]
        unmapped_batch: list[dict] = []

        mapped_batch = {}

        # Batch fetch: if this fails, mark all IDs in the batch as unmapped.
        logger.info("Processing batch of %s tax_ids", len(taxon_batch))
        # logger.debug("Batch tax_ids: %s", taxon_batch)
        try:
            reports = fetch_reports(taxon_batch, endpoint="taxonomy")
        except RuntimeError as exc:
            logger.error("Batch fetch failed for tax_ids %s: %s", taxon_batch, exc)
            for tax_id in taxon_batch:
                unmapped_batch.append(
                    {
                        "taxon_id": tax_id,
                        "error": str(exc),
                    }
                )
            return mapped_batch, unmapped_batch

        received_query_taxids: set[int | str] = set()
        for report in reports:
            query_taxid = get_report_query_taxid(report)
            if query_taxid is not None:
                received_query_taxids.add(query_taxid)

            sci_name = extract_sci_name(report)
            if not sci_name:
                logger.error("Unexpected response structure for tax_id %s", query_taxid)
                unmapped_batch.append(
                    {
                        "taxon_id": query_taxid,
                        "error": "unexpected response structure",
                    }
                )
                continue

            if sci_name is not None:
                # logger.debug("Mapped taxon %s", sci_name)
                mapped_batch.update(sci_name)
                continue

            error_reason = (((report.get("errors") or [{}])[0]).get("reason")) or "missing taxonomy"
            logger.warning("Tax_id %s returned error payload: %s", query_taxid, error_reason)
            unmapped_batch.append(
                {
                    "taxon_id": query_taxid,
                    "error": error_reason,
                }
            )
        # If API did not return a report for a requested ID, mark it explicitly.
        missing_taxids = [tax_id for tax_id in taxon_batch if tax_id not in received_query_taxids]
        for tax_id in missing_taxids:
            logger.warning("No report returned for requested tax_id %s", tax_id)
            unmapped_batch.append(
                {
                    "taxon_id": tax_id,
                    "error": "no report returned",
                }
            )

        return mapped_batch, unmapped_batch

    def extract_sci_name(report: dict) -> dict:
        taxonomy = report.get("taxonomy") or {}
        tax_id = taxonomy.get("tax_id")
        sci_name = (taxonomy.get("current_scientific_name") or {}).get("name")
        return {tax_id: sci_name}

    def process_parents(parent_taxids: list[int]) -> str:
        ordered_parents = []

        unique_parents = prepare_unique_parents(parent_taxids)
        no_of_parents = len(unique_parents)

        for taxon_batch in chunked(unique_parents, no_of_parents):
            mapped_parents, unmapped_parents = process_parent_batch(taxon_batch)

        for parent in unique_parents:
            if parent == 1 or parent == 131567:
                continue  # do not append taxon "root" or "cellular organisms"
            ordered_parent = mapped_parents.get(parent)
            ordered_parents.append(ordered_parent)

        string_lineage = "; ".join(ordered_parents)

        logger.debug(f"Mapped parents = {mapped_parents}")
        logger.debug(f"Unmapped parents = {unmapped_parents}")
        return string_lineage

    def get_taxon_w_org(reports: list[dict], organelle_type: str, taxid: int) -> str | None:
        """
        Checks API ouptut to determine if an organelle sequence is available for a species within that taxonomic rank.
        If so, returns the species name.
        """
        taxid_w_mito = {}
        for report in reports:
            if report.get("description") == organelle_type:
                organism_info = report.get("organism", [])
                scientific_name = organism_info.get("organism_name")
                if organelle_type == "Mitochondrion":
                    taxid_w_mito[taxid] = scientific_name
                    related_mitos.update(taxid_w_mito)
                return scientific_name
        return None

    def organelle_ref_lookup(
        taxid_lineage: list[int], species_taxid: int, organelle_type: str
    ) -> str | None:
        """
        Takes the taxonomic lineage and iterates in reverse order to find the lowest rank at which an organelle assembly is available.
        """
        rev_order_lineage = taxid_lineage[::-1]
        full_rev_lineage = rev_order_lineage.insert(0, species_taxid)
        # is_plant = 33090 in taxid_lineage

        for taxid in rev_order_lineage:
            if organelle_type == "Mitochondrion" and taxid in related_mitos:
                logger.debug(f"{taxid} found in the saved list")
                return related_mitos.get(taxid)
            if organelle_type == "Mitochondrion" and taxid in no_mitos:
                logger.debug(f"{taxid} found in the unsaved list")
                continue
            try:
                reports = fetch_reports([taxid], endpoint="organelle")
            except RuntimeError as exc:
                logger.error("Fetch failed for tax_id %s: %s", taxid, exc)
            if len(reports) == 0:
                logger.debug(f"No {organelle_type} found for {taxid}")
                no_mitos.append(taxid)
            else:
                taxon_check = get_taxon_w_org(reports, organelle_type, taxid)
                if taxon_check is not None:
                    return taxon_check

        return None


ncbi_taxonomy_service = NcbiTaxonomyService()

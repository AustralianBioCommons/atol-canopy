from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BulkOrganismImport(BaseModel):
    """Schema for bulk organism import.

    The API expects a dictionary with an 'organisms' key containing organism data.
    However, the data/unique_organisms.json file is directly a dictionary of organism data
    keyed by organism_grouping_key without a wrapping 'organisms' key.
    """

    organisms: Dict[
        str, Dict[str, Any]
    ]  # Dictionary of organism data keyed by organism_grouping_key


class BulkSampleImport(BaseModel):
    """Schema for bulk sample import.

    The API expects a dictionary with a 'samples' key containing sample data.
    However, the data/unique_samples.json file is directly a dictionary of sample data
    keyed by bpa_sample_id without a wrapping 'samples' key.
    """

    samples: Dict[str, Dict[str, Any]]  # Dictionary of sample data keyed by bpa_sample_id


class BulkExperimentImport(BaseModel):
    """Schema for bulk experiment import.

    The API expects a dictionary with an 'experiments' key containing experiment data.
    However, the data/experiments.json file is directly a dictionary of experiment data
    keyed by package_id without a wrapping 'experiments' key.
    """

    experiments: Dict[str, Dict[str, Any]]  # Dictionary of experiment data keyed by package_id


class BulkImportResponse(BaseModel):
    """Schema for bulk import response."""

    created_count: int
    skipped_count: Optional[int] = 0
    skipped_experiment_count: Optional[int] = 0
    skipped_run_count: Optional[int] = 0
    message: str
    debug: Optional[Dict[str, int]] = None

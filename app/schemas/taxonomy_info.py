from typing import Optional

from pydantic import BaseModel, ConfigDict


class TaxonomyInfoBase(BaseModel):
    busco_odb10_dataset_name: Optional[str] = None
    busco_odb12_dataset_name: Optional[str] = None
    find_plastid: Optional[bool] = None
    hic_motif: Optional[str] = None
    mitochondrial_genetic_code_id: Optional[int] = None
    mitohifi_reference_species: Optional[str] = None
    oatk_hmm_name: Optional[str] = None
    defined_class: Optional[str] = None
    augustus_dataset_name: Optional[str] = None
    genetic_code_id: Optional[int] = None


class TaxonomyInfoCreate(TaxonomyInfoBase):
    taxon_id: int


class TaxonomyInfoUpdate(TaxonomyInfoBase):
    pass


class TaxonomyInfoInDBBase(TaxonomyInfoBase):
    taxon_id: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TaxonomyInfo(TaxonomyInfoInDBBase):
    pass

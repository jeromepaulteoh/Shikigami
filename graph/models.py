from dataclasses import dataclass


@dataclass
class Node:
    id: int | None = None
    url: str = ""
    parent_url: str | None = None
    extraction_goal: str | None = None
    depth_from_seed: int | None = None
    section_type: str | None = None          # circular | guideline | notice | FAQ
    relevant_form_fields: str | None = None  # JSON array stored as string
    content_hash: str | None = None
    last_extracted_json: str | None = None   # JSON stored as string
    last_extracted_at: str | None = None
    created_at: str | None = None

"""CodebookVersionManager — applies change proposals to create new versions.

Pure Python logic, no LLM calls. Creates immutable CodebookVersion snapshots
and CodeMapping entries for retagging.
"""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async

if TYPE_CHECKING:
    from merism.models import Study

from merism.codebook.models import CodebookVersion, CodeChange, CodeMapping

logger = logging.getLogger(__name__)


@sync_to_async
def get_latest_version(study: Study) -> CodebookVersion | None:
    return CodebookVersion.objects.filter(study=study).first()


@sync_to_async
def create_initial_version(study: Study) -> CodebookVersion:
    """Create version 1 from the current Study.codebook field."""
    return CodebookVersion.objects.create(
        team=study.team,
        study=study,
        version=1,
        codes=list(study.codebook or []),
        source=CodebookVersion.Source.SEED,
    )


@sync_to_async
def apply_proposal(study: Study, change: CodeChange) -> CodebookVersion:
    """Apply a single CodeChange, producing a new CodebookVersion.

    Updates Study.codebook (the live field) and creates CodeMapping entries.
    """
    current = CodebookVersion.objects.filter(study=study).first()
    if current is None:
        current = CodebookVersion.objects.create(
            team=study.team, study=study, version=0,
            codes=list(study.codebook or []), source=CodebookVersion.Source.SEED,
        )

    new_codes = copy.deepcopy(current.codes)
    mappings: list[dict] = []

    if change.change_type == CodeChange.ChangeType.ADD:
        new_codes.append(change.payload["code"])

    elif change.change_type == CodeChange.ChangeType.MERGE:
        source_ids = set(change.payload["source_ids"])
        target_id = change.payload["target_id"]
        new_codes = [c for c in new_codes if c["code_id"] not in source_ids]
        for sid in source_ids:
            mappings.append({"old_code_id": sid, "new_code_id": target_id})

    elif change.change_type == CodeChange.ChangeType.SPLIT:
        source_id = change.payload["source_id"]
        new_codes = [c for c in new_codes if c["code_id"] != source_id]
        for target in change.payload["targets"]:
            new_codes.append(target)
        mappings.append({"old_code_id": source_id, "new_code_id": ""})

    elif change.change_type == CodeChange.ChangeType.RENAME:
        code_id = change.payload["code_id"]
        new_name = change.payload["new_name"]
        for c in new_codes:
            if c["code_id"] == code_id:
                c["name"] = new_name
                break

    elif change.change_type == CodeChange.ChangeType.DEPRECATE:
        code_id = change.payload["code_id"]
        replaced_by = change.payload.get("replaced_by", "")
        for c in new_codes:
            if c["code_id"] == code_id:
                c["status"] = "deprecated"
                break
        mappings.append({"old_code_id": code_id, "new_code_id": replaced_by})

    # Create new version
    new_version = CodebookVersion.objects.create(
        team=study.team,
        study=study,
        version=current.version + 1,
        codes=new_codes,
        source=CodebookVersion.Source.REVIEW,
    )

    # Create mappings
    for m in mappings:
        CodeMapping.objects.create(
            team=study.team,
            study=study,
            change=change,
            old_code_id=m["old_code_id"],
            new_code_id=m["new_code_id"],
            version=new_version,
        )

    # Update change record
    change.to_version = new_version
    change.status = CodeChange.Status.APPLIED
    change.save(update_fields=["to_version", "status", "updated_at"])

    # Sync live codebook on Study
    study.codebook = new_codes
    study.save(update_fields=["codebook", "updated_at"])

    logger.info(
        "codebook.version_manager.applied",
        extra={"study_id": str(study.id), "version": new_version.version, "change_type": change.change_type},
    )
    return new_version

from __future__ import annotations

import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from projects.legacy_bundle_library import open_server_bundle_for_import, safe_import_path
from projects.legacy_clara_import import (
    LegacyClaraImportError,
    find_legacy_clara_bundle_root,
    import_legacy_clara_bundle,
    import_legacy_clara_project_dir_bundle,
    is_legacy_clara_project_dir_bundle,
    legacy_clara_bundle_title,
    legacy_clara_project_dir_bundle_title,
)
from projects.models import LegacyProjectImport, Project


class Command(BaseCommand):
    help = "Idempotently bulk-import a configured legacy C-LARA bundle library."

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            required=True,
            help="Existing C-LARA-2 website username that will own newly imported projects (not a Linux username).",
        )
        parser.add_argument("--root", help="Bundle-library root; defaults to C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT.")
        parser.add_argument(
            "--metadata",
            help="Global metadata path, absolute or relative to --root; defaults to the configured metadata filename.",
        )
        parser.add_argument(
            "--source-system",
            default="clara_adelaide",
            help="Stable provenance namespace paired with each legacy project ID; default: clara_adelaide.",
        )
        parser.add_argument(
            "--library-version",
            default="",
            help="Conversion/library generation label such as v3; this may change without changing source identity.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Plan actions without changing the database or files.")
        parser.add_argument("--limit", type=int, help="Process at most this many ZIP-backed candidate rows.")
        parser.add_argument("--only-id", action="append", default=[], help="Process only this legacy ID; repeatable.")
        parser.add_argument("--retry-failed", action="store_true", help="Retry provenance records currently marked failed.")
        parser.add_argument(
            "--no-reconcile-existing",
            action="store_true",
            help="Do not match earlier manual imports using their legacy_import_summary.json metadata.",
        )
        parser.add_argument("--report", help="Optional JSONL report path.")

    def handle(self, *args, **options):
        root = self._library_root(options.get("root"))
        metadata_path = self._metadata_path(root, options.get("metadata"))
        rows = self._load_rows(metadata_path)
        owner = self._owner(options["owner"])
        source_system = str(options["source_system"] or "").strip()
        if not source_system:
            raise CommandError("--source-system must not be empty.")
        if options.get("limit") is not None and options["limit"] < 1:
            raise CommandError("--limit must be a positive integer.")

        only_ids = {str(value).strip() for value in options["only_id"] if str(value).strip()}
        candidates = [row for row in rows if self._has_payload(row)]
        if only_ids:
            candidates = [row for row in candidates if self._legacy_id(row) in only_ids]
            missing_ids = only_ids - {self._legacy_id(row) for row in candidates}
            if missing_ids:
                raise CommandError(f"Requested legacy IDs were not found with ZIP payloads: {', '.join(sorted(missing_ids))}")
        candidates.sort(key=self._row_sort_key)
        if options.get("limit") is not None:
            candidates = candidates[: options["limit"]]

        existing_projects = (
            {} if options["no_reconcile_existing"] else self._existing_imports_by_legacy_id(owner)
        )
        report_path = Path(options["report"]).expanduser().resolve() if options.get("report") else None
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("", encoding="utf-8")

        counts: Counter[str] = Counter()
        self.stdout.write(
            f"Library rows={len(rows)}; ZIP-backed candidates={len(candidates)}; "
            f"owner={owner.username}; dry_run={options['dry_run']}"
        )
        for index, row in enumerate(candidates, start=1):
            outcome = self._process_row(
                root=root,
                row=row,
                owner=owner,
                source_system=source_system,
                library_version=str(options["library_version"] or ""),
                dry_run=options["dry_run"],
                retry_failed=options["retry_failed"],
                existing_projects=existing_projects,
            )
            counts[outcome["status"]] += 1
            self.stdout.write(
                f"[{index}/{len(candidates)}] {outcome['legacy_project_id']} "
                f"{outcome['status']}: {outcome['message']}"
            )
            if report_path:
                with report_path.open("a", encoding="utf-8") as report:
                    report.write(json.dumps(outcome, ensure_ascii=False, default=str) + "\n")

        summary = ", ".join(f"{status}={count}" for status, count in sorted(counts.items())) or "no candidates"
        self.stdout.write(self.style.SUCCESS(f"Legacy bulk import complete: {summary}"))

    def _process_row(
        self,
        *,
        root: Path,
        row: dict[str, Any],
        owner,
        source_system: str,
        library_version: str,
        dry_run: bool,
        retry_failed: bool,
        existing_projects: dict[str, list[Project]],
    ) -> dict[str, Any]:
        legacy_id = self._legacy_id(row)
        base = {
            "source_system": source_system,
            "legacy_project_id": legacy_id,
            "title": str(row.get("title") or ""),
        }
        if not legacy_id:
            return {**base, "status": "invalid", "message": "metadata row has no stable legacy ID"}

        import_path = safe_import_path(root, row)
        if import_path is None or not import_path.exists():
            return {**base, "status": "invalid", "message": "payload path is missing or unsafe"}

        record = LegacyProjectImport.objects.filter(
            source_system=source_system,
            legacy_project_id=legacy_id,
        ).select_related("project").first()
        if record and record.status == LegacyProjectImport.STATUS_IMPORTED and record.project_id:
            return {
                **base,
                "status": "skipped_existing",
                "message": f"already imported as project {record.project_id}",
                "project_id": record.project_id,
            }
        if record and record.status == LegacyProjectImport.STATUS_FAILED and not retry_failed:
            return {**base, "status": "skipped_failed", "message": "use --retry-failed to retry the previous failure"}

        reconciled = existing_projects.get(legacy_id, [])
        if not record and len(reconciled) == 1:
            project = reconciled[0]
            if dry_run:
                return {
                    **base,
                    "status": "would_reconcile",
                    "message": f"would link existing project {project.id}",
                    "project_id": project.id,
                }
            record = self._new_record(
                row=row,
                root=root,
                import_path=import_path,
                owner=owner,
                source_system=source_system,
                legacy_id=legacy_id,
                library_version=library_version,
            )
            record.project = project
            record.status = LegacyProjectImport.STATUS_IMPORTED
            record.completed_at = timezone.now()
            record.diagnostics = ["Reconciled from an existing legacy_import_summary.json record."]
            record.save()
            return {
                **base,
                "status": "reconciled",
                "message": f"linked existing project {project.id}",
                "project_id": project.id,
            }
        if not record and len(reconciled) > 1:
            project_ids = [project.id for project in reconciled]
            return {
                **base,
                "status": "ambiguous_existing",
                "message": f"multiple existing projects match: {project_ids}",
                "project_ids": project_ids,
            }

        if dry_run:
            action = "retry" if record else "import"
            return {**base, "status": f"would_{action}", "message": f"would {action} {import_path.relative_to(root)}"}

        if record is None:
            record = self._new_record(
                row=row,
                root=root,
                import_path=import_path,
                owner=owner,
                source_system=source_system,
                legacy_id=legacy_id,
                library_version=library_version,
            )
        else:
            record.library_version = library_version
            record.bundle_relative_path = import_path.relative_to(root).as_posix()
            record.source_sha256 = str(row.get("sha256") or "")[:64]
            record.source_title = str(row.get("title") or "")[:200]
            record.original_owner_username = str(
                row.get("owner_username") or row.get("userid") or row.get("user_id") or ""
            )[:150]
        record.status = LegacyProjectImport.STATUS_IMPORTING
        record.project = None
        record.error = ""
        record.diagnostics = []
        record.attempt_count += 1
        record.started_at = timezone.now()
        record.completed_at = None
        record.save()

        try:
            with transaction.atomic():
                result, names = self._import_bundle(import_path, owner)
                diagnostics = list(result.diagnostics)
                if self._has_phonetic_layer(names):
                    diagnostics.append(
                        "Legacy phonetic files were detected but the phonetic layer was not imported into C-LARA-2 stages."
                    )
                self._persist_project_source(result.project)
                record.project = result.project
                record.status = LegacyProjectImport.STATUS_IMPORTED
                record.diagnostics = diagnostics
                record.error = ""
                record.completed_at = timezone.now()
                record.save()
            return {
                **base,
                "status": "imported",
                "message": f"created project {result.project.id} ({result.project.title})",
                "project_id": result.project.id,
                "diagnostics": diagnostics,
            }
        except Exception as exc:  # noqa: BLE001 - each bundle must fail independently
            record.status = LegacyProjectImport.STATUS_FAILED
            record.error = f"{type(exc).__name__}: {exc}"
            record.completed_at = timezone.now()
            record.save(update_fields=["status", "error", "completed_at", "updated_at"])
            return {**base, "status": "failed", "message": record.error}

    @staticmethod
    def _import_bundle(import_path: Path, owner):
        spool, _trace = open_server_bundle_for_import(import_path)
        with spool:
            with zipfile.ZipFile(spool) as archive:
                names = archive.namelist()
                if not names:
                    raise LegacyClaraImportError("ZIP file is empty.")
                legacy_root = find_legacy_clara_bundle_root(names)
                if legacy_root is not None:
                    title = Command._unique_title(owner, legacy_clara_bundle_title(archive, legacy_root))
                    result = import_legacy_clara_bundle(
                        zf=archive,
                        names=names,
                        root=legacy_root,
                        user=owner,
                        unique_title=title,
                    )
                    return result, names
                if is_legacy_clara_project_dir_bundle(names):
                    title = Command._unique_title(owner, legacy_clara_project_dir_bundle_title(archive))
                    result = import_legacy_clara_project_dir_bundle(
                        zf=archive,
                        names=names,
                        user=owner,
                        unique_title=title,
                    )
                    return result, names
                raise LegacyClaraImportError("Bundle is not a supported legacy C-LARA export.")

    @staticmethod
    def _persist_project_source(project: Project) -> None:
        source_dir = project.artifact_dir() / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "description.txt").write_text(project.description or "", encoding="utf-8")
        (source_dir / "source_text.txt").write_text(project.source_text or "", encoding="utf-8")

    @staticmethod
    def _unique_title(owner, base_title: str) -> str:
        candidate = (base_title or "Imported legacy C-LARA project").strip()[:200]
        if not Project.objects.filter(owner=owner, title=candidate).exists():
            return candidate
        for index in range(2, 10000):
            suffix = f" ({index})"
            titled = f"{candidate[: 200 - len(suffix)]}{suffix}"
            if not Project.objects.filter(owner=owner, title=titled).exists():
                return titled
        raise CommandError(f"Could not create a unique title for {candidate!r}.")

    @staticmethod
    def _new_record(*, row, root, import_path, owner, source_system, legacy_id, library_version):
        return LegacyProjectImport.objects.create(
            source_system=source_system,
            legacy_project_id=legacy_id,
            library_version=library_version,
            bundle_relative_path=import_path.relative_to(root).as_posix(),
            source_sha256=str(row.get("sha256") or "")[:64],
            source_title=str(row.get("title") or "")[:200],
            original_owner_username=str(
                row.get("owner_username") or row.get("userid") or row.get("user_id") or ""
            )[:150],
            imported_by=owner,
        )

    @staticmethod
    def _existing_imports_by_legacy_id(owner) -> dict[str, list[Project]]:
        matches: dict[str, list[Project]] = defaultdict(list)
        for project in Project.objects.filter(owner=owner).iterator():
            summaries = sorted((project.artifact_dir() / "runs").glob("*/legacy_import_summary.json"), reverse=True)
            for summary_path in summaries:
                try:
                    payload = json.loads(summary_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                metadata = payload.get("metadata") if isinstance(payload, dict) else None
                legacy_id = str(metadata.get("id") or "").strip() if isinstance(metadata, dict) else ""
                if legacy_id:
                    matches[legacy_id].append(project)
                    break
        return dict(matches)

    @staticmethod
    def _has_phonetic_layer(names: list[str]) -> bool:
        return any(
            any("phonetic" in part.casefold() for part in PurePosixPath(name).parts)
            for name in names
        )

    @staticmethod
    def _legacy_id(row: dict[str, Any]) -> str:
        return str(row.get("id") or row.get("directory_name") or "").strip()

    @staticmethod
    def _has_payload(row: dict[str, Any]) -> bool:
        return bool(row.get("has_zip") or row.get("zip_relative_path"))

    @classmethod
    def _row_sort_key(cls, row: dict[str, Any]):
        legacy_id = cls._legacy_id(row)
        try:
            return 0, int(legacy_id)
        except ValueError:
            return 1, legacy_id.casefold()

    @staticmethod
    def _library_root(value: str | None) -> Path:
        configured = value or getattr(settings, "LEGACY_CLARA_BUNDLE_LIBRARY_ROOT", "")
        if not configured:
            raise CommandError("Bundle-library root is not configured; pass --root.")
        root = Path(configured).expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f"Bundle-library root is not a directory: {root}")
        return root

    @staticmethod
    def _metadata_path(root: Path, value: str | None) -> Path:
        configured = value or getattr(settings, "LEGACY_CLARA_BUNDLE_LIBRARY_METADATA", "legacy_bundle_metadata.json")
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise CommandError("Legacy metadata file must be inside the library root.") from exc
        if not path.is_file():
            raise CommandError(f"Legacy metadata file does not exist: {path}")
        return path

    @staticmethod
    def _load_rows(path: Path) -> list[dict[str, Any]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read legacy metadata file {path}: {exc}") from exc
        rows = payload if isinstance(payload, list) else payload.get("bundles") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise CommandError("Legacy metadata must be a list or an object containing a bundles list.")
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _owner(username: str):
        try:
            return get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as exc:
            raise CommandError(f"C-LARA-2 user does not exist: {username}") from exc

from __future__ import annotations

import time
import uuid

from django.core.management.base import BaseCommand
from core import deployment_activity

from projects.views import (
    _claim_next_project_understanding_request,
    _count_queued_project_understanding_requests,
    _record_project_understanding_update,
    _release_project_understanding_request_lock,
    _run_project_understanding_task,
)


class Command(BaseCommand):
    help = "Process queued project-understanding Codex requests from a dedicated worker context."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one queued request and then exit.",
        )
        parser.add_argument(
            "--sleep-seconds",
            type=float,
            default=5.0,
            help="Seconds to sleep between queue polls when not using --once.",
        )
        parser.add_argument(
            "--worker-id",
            default="",
            help="Optional stable worker identifier to write into claimed request records.",
        )

    def handle(self, *args, **options):
        once = bool(options["once"])
        sleep_seconds = max(0.1, float(options["sleep_seconds"]))
        worker_id = options["worker_id"] or f"project-understanding-worker-{uuid.uuid4()}"
        self.stdout.write(f"Project-understanding worker starting as {worker_id}")

        while True:
            try:
                lease = deployment_activity.acquire('project-understanding')
            except deployment_activity.Maintenance:
                if once:
                    return
                time.sleep(sleep_seconds)
                continue
            try:
                claimed = _claim_next_project_understanding_request(worker_id)
            except BaseException:
                deployment_activity.release(lease)
                raise
            if claimed is None:
                deployment_activity.release(lease)
                queued_count = _count_queued_project_understanding_requests()
                if once:
                    self.stdout.write(f"No queued project-understanding requests found (queued={queued_count}).")
                    return
                time.sleep(sleep_seconds)
                continue

            report_id, payload = claimed
            user_id = payload.get("user_id")
            question = str(payload.get("question") or "").strip()
            if not question or user_id is None:
                try:
                    _record_project_understanding_update(
                        report_id=report_id,
                        user_id=user_id or 0,
                        message="Project-understanding worker found an invalid queued request; missing question or user id.",
                        status="error",
                    )
                finally:
                    try:
                        _release_project_understanding_request_lock(report_id)
                    finally:
                        deployment_activity.release(lease)
                if once:
                    return
                continue

            self.stdout.write(f"Processing project-understanding request {report_id}")
            try:
                _run_project_understanding_task(question, int(user_id), str(report_id))
            finally:
                try:
                    _release_project_understanding_request_lock(report_id)
                finally:
                    deployment_activity.release(lease)

            if once:
                return

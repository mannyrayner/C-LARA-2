from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from projects.management.commands.run_chunk_prompt_on_corpus import build_prompt, read_jsonl


class Command(BaseCommand):
    help = "Write one fully assembled chunk prompt for inspection."

    def add_arguments(self, parser):
        parser.add_argument("--input-jsonl", required=True)
        parser.add_argument("--prompt-file", required=True)
        parser.add_argument("--output-text", required=True)
        parser.add_argument("--prompt-kind", choices=("segmentation", "rating"), default="segmentation")
        parser.add_argument("--record-id", default="")
        parser.add_argument("--record-number", type=int, default=1, help="1-based record number used when --record-id is omitted.")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        input_path = Path(options["input_jsonl"]).resolve()
        prompt_path = Path(options["prompt_file"]).resolve()
        output_path = Path(options["output_text"]).resolve()
        if not input_path.exists():
            raise CommandError(f"input JSONL not found: {input_path}")
        if not prompt_path.exists():
            raise CommandError(f"prompt file not found: {prompt_path}")
        if output_path.exists() and not options["overwrite"]:
            raise CommandError(f"output text already exists: {output_path}; pass --overwrite")
        records = read_jsonl(input_path)
        if not records:
            raise CommandError(f"input JSONL contains no records: {input_path}")
        record = select_record(records, record_id=str(options["record_id"] or ""), record_number=int(options["record_number"] or 1))
        prompt = build_prompt(
            prompt_template=prompt_path.read_text(encoding="utf-8"),
            prompt_kind=str(options["prompt_kind"]),
            record=record,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt + "\n", encoding="utf-8")
        self.stdout.write("Wrote full chunk API prompt preview")
        self.stdout.write(f"Record: {record.get('record_id')}")
        self.stdout.write(f"Output: {output_path}")


def select_record(records: list[dict], *, record_id: str, record_number: int) -> dict:
    if record_id:
        for record in records:
            if str(record.get("record_id") or "") == record_id:
                return record
        raise CommandError(f"record id not found: {record_id}")
    index = record_number - 1
    if index < 0 or index >= len(records):
        raise CommandError(f"record number out of range: {record_number}")
    return records[index]

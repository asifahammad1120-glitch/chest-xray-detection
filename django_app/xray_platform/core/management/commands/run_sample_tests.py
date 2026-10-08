import csv
import random
from pathlib import Path

from django.core.management.base import BaseCommand

from core.ai_pipeline import run_full_pipeline, get_yolo_model


class Command(BaseCommand):
    help = "Runs the AI pipeline on sample images; saves annotated images and a results table"

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Folder with X-ray images")
        parser.add_argument("--labels", default=None, help="Folder with YOLO .txt labels (ground truth)")
        parser.add_argument("--out", required=True, help="Output folder")
        parser.add_argument("--count", type=int, default=12)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **opts):
        source = Path(opts["source"])
        labels_dir = Path(opts["labels"]) if opts["labels"] else None
        out = Path(opts["out"])
        out.mkdir(parents=True, exist_ok=True)

        images = sorted(p for p in source.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        random.Random(opts["seed"]).shuffle(images)
        images = images[: opts["count"]]

        names = get_yolo_model().names
        rows = []

        for img_path in images:
            result = run_full_pipeline(str(img_path))
            annotated_name = f"{img_path.stem[:40]}_annotated.jpg"
            result["annotated_image"].save(out / annotated_name, quality=90)

            # Ground truth classes from the YOLO label file, if provided
            gt_classes = set()
            if labels_dir:
                label_file = labels_dir / f"{img_path.stem}.txt"
                if label_file.exists():
                    for line in label_file.read_text().splitlines():
                        if line.strip():
                            gt_classes.add(names[int(line.split()[0])])

            yolo_classes = {d["class_name"] for d in result["detections"]}
            found = gt_classes & yolo_classes
            extra = yolo_classes - gt_classes

            rows.append({
                "image": annotated_name,
                "ground_truth": ", ".join(sorted(gt_classes)) or "-",
                "yolo_detections": "; ".join(
                    f"{d['class_name']} ({d['confidence']:.0%})" for d in result["detections"]) or "none",
                "cnn_classifications": "; ".join(
                    f"{d['classification_class']} ({d['classification_confidence']:.0%})"
                    for d in result["detections"]) or "none",
                "gt_found": f"{len(found)}/{len(gt_classes)}" if labels_dir else "-",
                "extra_classes": ", ".join(sorted(extra)) or "-",
            })
            self.stdout.write(f"Processed {img_path.name}")

        # CSV
        with open(out / "results.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        # Markdown table (paste straight into the report)
        header = "| Image | Ground truth | YOLO detections | CNN classification | GT classes found | Extra classes |\n|---|---|---|---|---|---|\n"
        body = "".join(
            f"| {r['image']} | {r['ground_truth']} | {r['yolo_detections']} | {r['cnn_classifications']} | {r['gt_found']} | {r['extra_classes']} |\n"
            for r in rows
        )
        (out / "results.md").write_text(header + body, encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Done. {len(rows)} images saved to {out}"))
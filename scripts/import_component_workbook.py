"""Import explicitly listed China-market component models from a reviewed workbook.

The reference export keeps every workbook row. Only models individually listed
on China-market manufacturer pages or datasheets enter the runtime catalog.
Static front/back loads remain separate from wind and snow loads.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NAMESPACE = {"m": MAIN}
EXACT_METHOD = "\u5b98\u7f51\u9010\u9879\u5217\u793a"
CHINA_MARKETS = {"\u4e2d\u56fd", "cn"}
RETRIEVED_AT = "2026-10-01T00:00:00+08:00"


def workbook_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    with ZipFile(path) as workbook:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
            strings = [
                "".join(text.text or "" for text in item.findall(".//m:t", NAMESPACE))
                for item in root.findall("m:si", NAMESPACE)
            ]

        sheet = ElementTree.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        records: list[tuple[int, dict[str, str]]] = []
        for row in sheet.findall(".//m:sheetData/m:row", NAMESPACE):
            number = int(row.attrib["r"])
            if number < 6:
                continue
            values: dict[str, str] = {}
            for cell in row.findall("m:c", NAMESPACE):
                column = re.match(r"[A-Z]+", cell.attrib["r"])
                if column is None:
                    continue
                value = cell.find("m:v", NAMESPACE)
                inline = cell.find("m:is", NAMESPACE)
                if value is not None:
                    text = value.text or ""
                    if cell.attrib.get("t") == "s":
                        text = strings[int(text)]
                elif inline is not None:
                    text = "".join(
                        item.text or "" for item in inline.findall(".//m:t", NAMESPACE)
                    )
                else:
                    text = ""
                values[column.group()] = text.strip()
            if values.get("B"):
                records.append((number, values))
    return records


def optional_number(value: str) -> float | None:
    return float(value) if value else None


def build_records(
    rows: list[tuple[int, dict[str, str]]],
    source_file: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    reference: list[dict[str, object]] = []
    active: list[dict[str, object]] = []
    for number, row in rows:
        url = row.get("M", "")
        if not url.startswith("https://"):
            raise ValueError(f"row {number}: official source must use HTTPS")
        eligible = row.get("J") == EXACT_METHOD and row.get("K") in CHINA_MARKETS
        record: dict[str, object] = {
            "workbook_row": number,
            "manufacturer": row.get("A", ""),
            "component_model": row["B"],
            "rated_power_w": optional_number(row.get("C", "")),
            "front_static_load_pa": optional_number(row.get("D", "")),
            "back_static_load_pa": optional_number(row.get("E", "")),
            "snow_load_pa": optional_number(row.get("F", "")),
            "wind_load_pa": optional_number(row.get("G", "")),
            "hail_resistance_mm": optional_number(row.get("H", "")),
            "hail_impact_velocity_m_s": optional_number(row.get("I", "")),
            "model_derivation_method": row.get("J", ""),
            "market_version": row.get("K", ""),
            "source_document_type": row.get("L", ""),
            "source_url": url,
            "source_note": row.get("N", ""),
            "auto_match_eligible": eligible,
        }
        reference.append(record)
        if not eligible:
            continue

        profile = {key: value for key, value in record.items() if key in {
            "component_model", "manufacturer", "rated_power_w",
            "front_static_load_pa", "back_static_load_pa",
            "snow_load_pa", "wind_load_pa", "hail_resistance_mm",
            "hail_impact_velocity_m_s", "market_version",
            "model_derivation_method", "source_document_type", "source_note",
            "source_url",
        }}
        profile["source_name"] = f"{source_file}, row {number}; manufacturer source linked"
        profile["retrieved_at"] = RETRIEVED_AT
        profile["match_confidence"] = 0.9
        profile["parameter_sources"] = {
            key: url for key in (
                "rated_power_w", "front_static_load_pa", "back_static_load_pa",
                "snow_load_pa", "wind_load_pa", "hail_resistance_mm",
                "hail_impact_velocity_m_s",
            ) if record[key] is not None
        }
        profile["lookup_notes"] = [
            "Match the exact nameplate model and market version before underwriting.",
            "Front/back static loads are reference values, not wind or snow load ratings.",
        ]
        if row.get("N"):
            profile["lookup_notes"].append(row["N"])
        active.append(profile)
    return reference, active


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    rows = workbook_rows(args.workbook)
    reference, active = build_records(rows, args.workbook.name)

    sample = json.loads(
        (project_root / "data/examples/component_catalog.sample.json")
        .read_text(encoding="utf-8-sig")
    )
    catalog = [*sample, *active]
    models = [re.sub(r"[^a-z0-9]", "", str(x["component_model"]).casefold()) for x in catalog]
    duplicates = [model for model, count in Counter(models).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate normalized models: {duplicates}")

    reference_path = project_root / "data/reference/component_parameters_2026-10-01.json"
    catalog_path = project_root / "data/catalogs/component_catalog_2026-10-01.json"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_file": args.workbook.name,
        "source_sha256": hashlib.sha256(args.workbook.read_bytes()).hexdigest(),
        "records": reference,
    }
    reference_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"reference rows: {len(reference)} -> {reference_path}")
    print(f"runtime profiles: {len(catalog)} ({len(active)} newly eligible) -> {catalog_path}")


if __name__ == "__main__":
    main()

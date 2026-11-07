"""Release 455: strictly bounded weekly nutrition CSV formatting.

Pure formatting function; never opens databases or performs writes.
"""
import csv
import io

from .worker_week454 import days454

from .secondary_nutrients463 import NUTRIENTS, MICROS

FIELDS = (
    "date",
    "calories_kcal",
    "protein_g",
    "carbohydrates_g",
    "fat_g",
    "fiber_g",
    "water_fl_oz",
    "water_target_fl_oz",
    "food_entries_shown",
    "has_more_entries",
    "calories_coverage",
    "protein_coverage",
    "carbohydrates_coverage",
    "fat_coverage",
    "fiber_coverage",
) + tuple(
    key.replace("-", "_") + "_" + unit
    for key, _, unit in MICROS
) + tuple(
    key.replace("-", "_") + "_coverage"
    for key, _, _ in MICROS
)

COLUMN = {
    "energy": "calories_kcal",
    "proteins": "protein_g",
    "carbohydrates": "carbohydrates_g",
    "fat": "fat_g",
    "fiber": "fiber_g",
    **{
        key: key.replace("-", "_") + "_" + unit
        for key, _, unit in MICROS
    },
}


COVERAGE_COLUMN = {
    "energy": "calories_coverage",
    "proteins": "protein_coverage",
    "carbohydrates": "carbohydrates_coverage",
    "fat": "fat_coverage",
    "fiber": "fiber_coverage",
    **{
        key: key.replace("-", "_") + "_coverage"
        for key, _, _ in MICROS
    },
}


def render_week_csv455(reports, end_day):
    expected = days454(end_day)

    if (
        type(reports) is not list
        or len(reports) != 7
        or [report["day"] for report in reports] != expected
    ):
        raise ValueError("Invalid weekly CSV date coverage")

    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=FIELDS,
        lineterminator="\r\n",
        extrasaction="raise",
    )
    writer.writeheader()

    for report in reports:
        row = {
            "date": report["day"],
            "water_fl_oz": report["water_oz"],
            "water_target_fl_oz": report["water_target_oz"],
            "food_entries_shown": len(report["items"]),
            "has_more_entries": (
                "yes" if report["has_more"] else "no"
            ),
        }

        for key in NUTRIENTS:
            reported = report["coverage"].get(key, 0)
            row[COLUMN[key]] = (
                report["totals"].get(key, 0.0)
                if reported else ""
            )
            row[COVERAGE_COLUMN[key]] = reported

        writer.writerow(row)

    return output.getvalue()

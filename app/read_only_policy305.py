"""Reviewed display fields shared by both SQLite browsing interfaces.
Unknown tables and fields are never displayed.
"""

# Explicit non-sensitive views. Do not expose arbitrary future tables.
VIEWER_COLUMNS = {
    "compounds": ("id", "name", "category", "primary_unit"),
    "vials": ("id", "compound_id", "purchase_id", "label", "lot", "form", "content_value", "content_unit", "status", "expires_on"),
    "purchases": ("id", "vendor", "purchased_on", "shipping_cents", "tax_cents", "discount_cents"),
    "supplies": ("id", "purchase_id", "name", "kind", "purchased_qty", "remaining_qty"),
    "dose_logs": ("id", "vial_id", "taken_at", "amount_base", "kind"),
    "vital_readings": ("id", "measured_at", "weight_kg", "systolic", "diastolic", "pulse_bpm"),
    "protocols": ("id", "name", "is_active", "start_date", "end_date"),
}

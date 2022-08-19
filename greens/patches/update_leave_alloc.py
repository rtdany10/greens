import frappe
from frappe.utils import add_to_date, get_first_day, today


def execute():
    # last_month = add_to_date(get_first_day(today()), days=-1)
    last_month_start = get_first_day(today())
    ll_to_fix = frappe.db.get_all("Leave Ledger Entry", filters={
        # "to_date": last_month,
        "from_date": [">", last_month_start],
        "docstatus": 1
    }, pluck="name")
    for ll in ll_to_fix:
        frappe.db.set_value("Leave Ledger Entry", ll, "from_date", last_month_start)

import frappe
from frappe.utils import get_first_day, get_last_day, today

from greens.tasks import allocate_leave


def execute():
    # last_month = add_to_date(get_first_day(today()), days=-1)
    month_start = get_first_day(today())
    month_end = get_last_day(today())
    ll_to_fix = frappe.db.get_all("Leave Allocation", filters={
        # "to_date": last_month,
        "from_date": ["between", [month_start, month_end]],
        "docstatus": 1,
		"leave_type": "Weekly Off"
    }, fields=["name", "employee"])
    for ll in ll_to_fix:
        doc = frappe.get_doc("Leave Allocation", ll["name"])
        doc.cancel()
        doc.delete()
        allocate_leave(
            frappe.get_last_doc('Attendance', filters={
                "docstatus": 1,
                "status": "Present",
                "attendance_date": ["between", [month_start, month_end]],
                "employee": ll["employee"]
            })
        )

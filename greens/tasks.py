# Copyright (c) 2021, Wahni Green Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import flt, get_first_day, get_last_day, today

from erpnext.hr.utils import create_additional_leave_ledger_entry, get_leave_allocations


@frappe.whitelist()
def allocate_leave():
	today_date = today()
	month_start = get_first_day(today_date)
	leave_type = frappe.get_doc("Leave Type", 'Weekly Off')

	employee = frappe.get_all("Attendance", filters = {
		"attendance_date": ["between", [month_start, today_date]],
		"docstatus": 1
	}, fields = ["DISTINCT(employee) as employee"])

	for emp in employee:
		marked_days = emp["marked_days"]
		if marked_days >= 6:
			leave_allocations = get_leave_allocations(today_date, leave_type.name)
			earned_leaves = 0
			if marked_days == 9:
				earned_leaves += 1.5
			if marked_days == 15:
				earned_leaves += 1.5
			if marked_days == 21:
				earned_leaves += 1.5

			for d in leave_allocations:
				allocation = frappe.get_doc('Leave Allocation', d.name)
				new_allocation = flt(allocation.total_leaves_allocated) + flt(earned_leaves)
				if new_allocation > leave_type.max_leaves_allowed and leave_type.max_leaves_allowed > 0:
					new_allocation = leave_type.max_leaves_allowed
				if new_allocation != allocation.total_leaves_allocated:
					allocation.db_set("total_leaves_allocated", new_allocation, update_modified=False)
					create_additional_leave_ledger_entry(allocation, earned_leaves, today_date)

			if not leave_allocations:
				frappe.get_doc({
					'doctype': 'Leave Allocation',
					'employee': emp,
					'leave_type': leave_type.name,
					'from_date': month_start,
					'to_date': get_last_day(today_date),
					'new_leaves_allocated': flt(earned_leaves)
				}).submit()
	return

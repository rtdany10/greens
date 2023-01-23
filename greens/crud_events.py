# Copyright (c) 2022, Wahni Green Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import copy

import frappe
from erpnext.hr.doctype.employee_checkin.employee_checkin import \
				calculate_working_hours
from erpnext.hr.utils import create_additional_leave_ledger_entry
from frappe.utils import add_to_date, flt, get_first_day, get_last_day


def calculate_emp_overtime(doc, method=None):
	if flt(doc.working_hours) >= 10.5:
		filters = {
			"employee": doc.employee,
			"time": ("between", (doc.attendance_date, doc.attendance_date)),
			"shift": doc.shift,
		}
		logs = frappe.db.get_list(
			"Employee Checkin", fields="*", filters=filters, order_by="employee,time"
		)
		ten_pm = add_to_date(doc.attendance_date, hours=22)
		ot_log = [d for d in logs if d.time > ten_pm]
		if not ot_log:
			return

		ten_pm_log = copy.deepcopy(logs[0])
		ten_pm_log['time'] = ten_pm
		ot_log.insert(0, ten_pm_log)
		overtime_above_ten = calculate_working_hours(
			ot_log,
			"Alternating entries as IN and OUT during the same shift",
			"Every Valid Check-in and Check-out",
		)[0]

		doc.ot_above_ten = overtime_above_ten if overtime_above_ten > 0 else 0
		doc.ot_below_ten = doc.working_hours - doc.ot_above_ten - 9.5
		if doc.ot_below_ten < 0:
			doc.ot_below_ten = 0


def allocate_leave(doc, method=None):
	if doc.status not in ["Present", "Half Day"]:
		return

	month_start = get_first_day(doc.attendance_date)
	month_end = get_last_day(doc.attendance_date)
	leave_type = frappe.get_cached_value(
		"Leave Type",
		(frappe.db.get_single_value('HR Settings', 'auto_allocated_leave_type') or "Weekly Off"),
		['name', 'max_leaves_allowed'],
		as_dict=1
	)

	attendance = frappe.get_all("Attendance", filters={
		"attendance_date": ["between", [month_start, month_end]],
		"docstatus": 1,
		"employee": doc.employee,
		"status": ["in", ["Present"]]
	}, fields=["COUNT(name) as marked_days"], group_by="status", order_by="status desc")

	if not attendance:
		return
	marked_days = attendance[0].marked_days
	if marked_days < 6:
		return
	earned_leaves = 1 if marked_days == 6 else (
		(
			0.5 * int((marked_days - 6) / 3)
		) + 1
	)
	if not earned_leaves:
		return

	leave_allocations = get_leave_allocations(doc.employee, month_end, leave_type.name)
	for d in leave_allocations:
		allocation = frappe.get_doc("Leave Allocation", d.name)
		to_allocate = abs(flt(allocation.total_leaves_allocated) - flt(earned_leaves))
		if (earned_leaves > leave_type.max_leaves_allowed and leave_type.max_leaves_allowed > 0):
			earned_leaves = leave_type.max_leaves_allowed
			to_allocate = earned_leaves - flt(allocation.total_leaves_allocated)
			if to_allocate <= 0:
				continue
		if earned_leaves != allocation.total_leaves_allocated:
			allocation.db_set("total_leaves_allocated", earned_leaves, update_modified=False)
			create_additional_leave_ledger_entry(allocation, to_allocate, month_start)

	if not leave_allocations:
		frappe.get_doc({
			"doctype": "Leave Allocation",
			"employee": doc.employee,
			"leave_type": leave_type.name,
			"from_date": month_start,
			"to_date": month_end,
			"new_leaves_allocated": flt(earned_leaves)
		}).submit()


def get_leave_allocations(emp, date, leave_type):
	leave_alloc = frappe.qb.DocType('Leave Allocation')
	return (
		frappe.qb.from_(leave_alloc).select(leave_alloc.name)
		.where(leave_alloc.employee == emp).where(date >= leave_alloc.from_date)
		.where(date <= leave_alloc.to_date).where(leave_alloc.docstatus == 1)
		.where(leave_alloc.leave_type == leave_type).run(as_dict=True)
	)

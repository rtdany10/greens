# Copyright (c) 2021, Wahni Green Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.hr.doctype.employee_checkin.employee_checkin import (
	calculate_working_hours,
)
from erpnext.hr.utils import (
	create_additional_leave_ledger_entry,
	get_holiday_dates_for_employee,
)
from frappe.utils import (
	add_to_date,
	flt,
	get_datetime,
	get_first_day,
	get_last_day,
	month_diff,
	now,
	today,
)


def salary_slip(doc, method=None):
	retirement = frappe.db.get_value("Employee", doc.employee, "date_of_retirement")
	if retirement and not month_diff(today(), retirement):
		doc.is_retiring = 1
	holidays = get_holiday_dates_for_employee(doc.employee, doc.start_date, doc.end_date)
	if holidays:
		attendance = frappe.get_all("Attendance", filters={
				"attendance_date": ["in", holidays],
				"docstatus": 1,
				"employee": doc.employee,
				"status": ["in", ["Present", "Half Day"]]
			},
			fields=["COUNT(name) as count", "status"],
			group_by="status"
		)
		if attendance:
			holiday_working = 0
			for d in attendance:
				if d["status"] == "Present":
					holiday_working += 1
				else:
					holiday_working += 0.5
			doc.holiday_working = holiday_working

	ot_logs = frappe.get_all("Attendance", filters={
			"attendance_date": ["between", [doc.start_date, doc.end_date]],
			"docstatus": 1,
			"employee": doc.employee,
		},
		fields=["SUM(ot_below_ten) as overtime", "SUM(ot_above_ten) as overtime_after_ten"],
		group_by="employee",
	)
	if ot_logs:
		doc.overtime = ot_logs[0]["overtime"]
		doc.ot_after_ten = ot_logs[0]["overtime_after_ten"]

def allocate_leave(doc, method=None):
	if not doc.status in ["Present", "Half Day"]:
		return

	today_date = today()
	month_start = get_first_day(today_date)
	leave_type = frappe.get_doc("Leave Type", "Weekly Off")

	attendance = frappe.get_all("Attendance", filters={
			"attendance_date": ["between", [month_start, today_date]],
			"docstatus": 1,
			"employee": doc.employee,
			"status": ["in", ["Present"]]
		},
		fields=["COUNT(name) as marked_days"],
		group_by="status",
		order_by="status desc"
	)

	if not attendance:
		return
	marked_days = attendance[0].marked_days
	if marked_days < 6:
		return
	earned_leaves = 1 if marked_days == 6 else (0.5 if marked_days % 3 == 0 else 0)
	if not earned_leaves:
		return

	leave_allocations = get_leave_allocations(doc.employee, today_date, leave_type.name)
	for d in leave_allocations:
		allocation = frappe.get_doc("Leave Allocation", d.name)
		new_allocation = flt(allocation.total_leaves_allocated) + flt(earned_leaves)
		if (new_allocation > leave_type.max_leaves_allowed and leave_type.max_leaves_allowed > 0):
			new_allocation = leave_type.max_leaves_allowed
		if new_allocation != allocation.total_leaves_allocated:
			allocation.db_set("total_leaves_allocated", new_allocation, update_modified=False)
			create_additional_leave_ledger_entry(allocation, earned_leaves, today_date)

	if not leave_allocations:
		frappe.get_doc({
			"doctype": "Leave Allocation",
			"employee": doc.employee,
			"leave_type": leave_type.name,
			"from_date": month_start,
			"to_date": get_last_day(today_date),
			"new_leaves_allocated": flt(earned_leaves)
		}).submit()


def get_leave_allocations(emp, date, leave_type):
	return frappe.db.sql("""select name
		from `tabLeave Allocation`
		where
			employee=%s and
			%s between from_date and to_date and docstatus=1
			and leave_type=%s""",
	(emp, date, leave_type), as_dict=1)

def attendance(doc, method=None):
	overtime = 0.00
	logs = frappe.db.get_all("Employee Checkin", fields=["*"],
		filters=[
			["employee", "=", doc.employee],
			["time", "between", [doc.attendance_date, add_to_date(doc.attendance_date, days=1)]],
		],
		order_by="time",
	)

	total_working_hours = calculate_working_hours(
		logs,
		"Alternating entries as IN and OUT during the same shift",
		"Every Valid Check-in and Check-out",
	)[0]

	if doc.status == "Half Day":
		if total_working_hours < 5:
			frappe.throw("Minimum 5 hours of work time is required for half-day.")

	if total_working_hours >= 10.5:
		overtime += (total_working_hours - 9.5)
		in_time = get_datetime(add_to_date(doc.attendance_date, hours=22))
		if logs[-1].time > in_time:
			ot_log = [d for d in logs if d.time >= in_time]
			overtime_above_ten = calculate_working_hours(
				ot_log,
				"Alternating entries as IN and OUT during the same shift",
				"Every Valid Check-in and Check-out",
			)[0]
			overtime -= overtime_above_ten
			doc.ot_above_ten = overtime_above_ten
		doc.ot_below_ten = overtime if overtime > 0 else 0

def shift_checkout():
	condition = [add_to_date(today(), days=-1), today()]
	checkins = frappe.get_all("Employee Checkin", filters=[
			["time", "between", condition],
		],
		fields=["count(name) as count", "employee"],
		group_by="employee"
	)
	for emp in checkins:
		if emp["count"] % 2 == 0:
			continue
		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": emp["employee"],
			"time": add_to_date(today(), days=-1, hours=23, minutes=59, seconds=59),
		}).insert(ignore_permissions=True)

def employee_checkout(doc, method=None):
	doc_date = get_datetime(doc.time).date()
	out_time = get_datetime(add_to_date(doc_date, hours=22))
	if get_datetime(doc.time) < out_time:
		return
	try:
		last_in = frappe.get_last_doc('Employee Checkin', filters=[
				["employee", "=", doc.employee],
			],
			order_by="time desc"
		)
	except Exception:
		return
	else:
		if last_in and last_in.time < out_time:
			frappe.get_doc({
				"doctype": "Employee Checkin",
				"employee": doc.employee,
				"log_type": "OUT",
				"time": add_to_date(doc_date, hours=21, minutes=59, seconds=59),
			}).insert(ignore_permissions=True)

			frappe.get_doc({
				"doctype": "Employee Checkin",
				"employee": doc.employee,
				"log_type": "IN",
				"time": out_time,
			}).insert(ignore_permissions=True)

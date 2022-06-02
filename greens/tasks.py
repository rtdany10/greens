# Copyright (c) 2022, Wahni Green Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.hr.doctype.attendance.attendance import \
				mark_attendance as mark_day
from erpnext.hr.doctype.employee_checkin.employee_checkin import \
				calculate_working_hours
from erpnext.hr.doctype.leave_application.leave_application import \
				get_leave_approver
from erpnext.hr.utils import create_additional_leave_ledger_entry
from frappe.query_builder.functions import Count
from frappe.utils import (add_to_date, flt, get_datetime, get_first_day,
                          get_last_day, today)


def allocate_leave(doc, method=None):
	if doc.status not in ["Present", "Half Day"]:
		return

	today_date = today()
	month_start = get_first_day(today_date)
	leave_type = frappe.get_cached_value(
		"Leave Type",
		(frappe.db.get_single_value('HR Settings', 'auto_allocated_leave_type') or "Weekly Off"),
		['name', 'max_leaves_allowed'],
		as_dict=1
	)

	attendance = frappe.get_all("Attendance", filters={
		"attendance_date": ["between", [month_start, today_date]],
		"docstatus": 1,
		"employee": doc.employee,
		"status": ["in", ["Present"]]
	}, fields=["COUNT(name) as marked_days"], group_by="status", order_by="status desc")

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
	leave_alloc = frappe.qb.DocType('Leave Allocation')
	return (
		frappe.qb.from_(leave_alloc).select(leave_alloc.name)
		.where(leave_alloc.employee == emp).where(date >= leave_alloc.from_date)
		.where(date <= leave_alloc.to_date).where(leave_alloc.docstatus == 1)
		.where(leave_alloc.leave_type == leave_type).run(as_dict=True)
	)


def daily_attendance():
	try:
		link_attendance()
		shift_checkout()
		mark_attendance()
		frappe.enqueue('greens.tasks.mark_absence', queue='long', enqueue_after_commit=True)
	except Exception as e:
		frappe.log_error(str(e), "Daily Attendance Error")


def link_attendance():
	yesterday = add_to_date(today(), days=-1)
	checkins = frappe.get_all("Employee Checkin", filters=[
		["time", "between", [yesterday, yesterday]],
		["attendance", "in", ["", None]],
	], fields=["name", "employee", "shift"])
	for doc in checkins:
		try:
			attendance = frappe.get_last_doc('Attendance', filters={
				'employee': doc.employee,
				'attendance_date': yesterday,
				'docstatus': ('!=', '2')
			})
		except Exception:
			attendance = frappe.get_doc({
				'doctype': 'Attendance',
				'employee': doc.employee,
				'attendance_date': yesterday,
				'status': "Present",
				'company': frappe.db.get_value('Employee', doc.employee, 'company'),
				'shift': doc.shift,
			})
			attendance.flags.ignore_validate = True
			attendance.insert(ignore_permissions=True)
		finally:
			frappe.db.set_value("Employee Checkin", doc.name, 'attendance', attendance.name)


def shift_checkout():
	yesterday = add_to_date(today(), days=-1)
	checkins = frappe.get_all("Employee Checkin", filters=[
		["time", "between", [yesterday, yesterday]],
	], fields=["count(name) as count", "employee", "shift_end"], group_by="employee")
	for emp in checkins:
		if emp["count"] % 2 == 0:
			continue
		try:
			frappe.get_doc({
				"doctype": "Employee Checkin",
				"employee": emp["employee"],
				"time": emp["shift_end"] or add_to_date(yesterday, hours=22),
				"auto_checkout": 1
			}).insert(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(str(e), "Daily Shift Checkout Error")
			continue


def mark_attendance():
	attendance = frappe.db.get_all("Attendance", filters={
		'attendance_date': [">=", "2022-01-15"],
		'processed': 0,
		'docstatus': 0
	}, pluck="name")
	for att in attendance:
		try:
			overtime = 0.00
			doc = frappe.get_doc("Attendance", att)
			logs = frappe.db.get_all("Employee Checkin", fields=["*"], filters=[
				["employee", "=", doc.employee],
				["time", "between", [doc.attendance_date, doc.attendance_date]],
			], order_by="time")

			total_working_hours = calculate_working_hours(
				logs,
				"Alternating entries as IN and OUT during the same shift",
				"Every Valid Check-in and Check-out",
			)[0]

			doc.flags.ignore_validate = True
			doc.working_hours = total_working_hours
			doc.processed = 1

			if frappe.db.get_value("Employee", doc.employee, "employment_type") == "Part-time":
				doc.status = "Present"
				doc.submit()
				continue

			if total_working_hours < 9.5:
				for log in logs:
					if log.shift:
						doc.late_entry = 1 if logs[0].time > log.shift_start else 0
						doc.early_exit = 1 if logs[-1].time < log.shift_end else 0
						break

			if total_working_hours >= 5:
				doc.status = "Present" if total_working_hours >= 7 else "Half Day"
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
				doc.submit()
			else:
				doc.status = "Absent"
				doc.save()
		except Exception as e:
			frappe.log_error(str(e), "Daily Attendance Marking Error - " + str(att))
			continue


def employee_checkout(doc, method=None):
	doc_date = get_datetime(doc.time).date()
	out_time = get_datetime(add_to_date(doc_date, hours=22))
	if doc.log_type or get_datetime(doc.time) <= out_time:
		return
	try:
		last_in = frappe.get_last_doc('Employee Checkin', filters=[
			["employee", "=", doc.employee],
		], order_by="time desc")
	except Exception:
		return
	else:
		checkins = frappe.get_all("Employee Checkin", filters=[
			["time", "between", [doc_date, doc_date]],
			["employee", "=", doc.employee],
		], fields=["count(name) as count"], group_by="employee")
		if checkins and checkins[0]["count"] % 2 == 0:
			return
		if last_in.time < out_time:
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
				"time": add_to_date(doc_date, hours=22, seconds=1),
			}).insert(ignore_permissions=True)


def clear_duplicate_checkin():
	checkin = frappe.qb.DocType('Employee Checkin')
	duplicate = frappe.qb.from_(checkin).select(checkin.name)\
		.groupby(checkin.time).groupby(checkin.employee)\
		.having(Count(checkin.name) > 1).run(as_dict=True)
	for d in duplicate:
		frappe.delete_doc('Employee Checkin', d.name, ignore_missing=True, force=True)


def mark_absence():
	yesterday = add_to_date(today(), days=-1)
	active_emp = frappe.db.get_all('Employee', {'status': 'Active'}, pluck='name')

	exclude_emp = frappe.db.get_all("Attendance", filters={
		'attendance_date': ["=", yesterday],
		'docstatus': ['!=', 2]
	}, pluck="employee")

	active_emp = list(set(active_emp).difference(exclude_emp))
	leave_type = frappe.get_cached_value('HR Settings', None, 'auto_allocated_leave_type') or "Weekly Off"

	for emp in active_emp:
		try:
			leave_allocations, leaves = get_leave_allocations(emp, yesterday, leave_type), 0
			if leave_allocations:
				for d in leave_allocations:
					leaves += int(frappe.db.get_value("Leave Allocation", d.name, 'total_leaves_allocated'))
				if leaves:
					mark_leave(emp, yesterday, leave_type)
					continue

			mark_day(emp, yesterday, 'Absent')
		except Exception as e:
			frappe.log_error(str(e), "Daily Absence Marking Error - " + str(emp))
			continue


def mark_leave(emp, date, leave_type):
	doc_dict = {
		'doctype': 'Leave Application',
		'employee': emp,
		'leave_type': leave_type,
		'from_date': date,
		'to_date': date,
		'leave_approver': get_leave_approver(emp),
		'status': 'Approved'
	}
	frappe.get_doc(doc_dict).submit()


@frappe.whitelist()
def update_attendance(from_date, to_date, device):
	frappe.enqueue(
		'greens.tasks._update_attendance', queue='long',
		from_date=from_date, to_date=to_date, device=device
	)
	frappe.msgprint("Job enqueued")


def _update_attendance(from_date, to_date, device):
	to_process = []
	while(from_date <= to_date):
		checkins = frappe.get_all("Employee Checkin", filters=[
			["time", "between", [from_date, from_date]],
		], fields=["count(name) as count", "employee", "shift_end"], group_by="employee")
		for emp in checkins:
			if emp["count"] % 2 == 0:
				continue
			try:
				frappe.get_doc({
					"doctype": "Employee Checkin",
					"employee": emp["employee"],
					"time": emp["shift_end"] or add_to_date(from_date, hours=22),
					"auto_checkout": 1
				}).insert(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(str(e), "Daily Shift Checkout Error")
				continue

		checkins = frappe.get_all("Employee Checkin", filters=[
			["time", "between", [from_date, from_date]],
			["attendance", "in", ["", None]],
			["device_id", "=", device],
		], fields=["name", "employee", "shift"])
		for doc in checkins:
			try:
				attendance = frappe.get_last_doc('Attendance', filters={
					'employee': doc.employee,
					'attendance_date': from_date,
					'docstatus': ('!=', '2')
				})
			except Exception:
				attendance = frappe.get_doc({
					'doctype': 'Attendance',
					'employee': doc.employee,
					'attendance_date': from_date,
					'status': "Present",
					'company': frappe.db.get_value('Employee', doc.employee, 'company'),
					'shift': doc.shift,
				})
				attendance.flags.ignore_validate = True
				attendance.insert(ignore_permissions=True)
			else:
				if attendance.docstatus == 1:
					attendance.cancel()
					attendance = frappe.get_doc({
						'doctype': 'Attendance',
						'employee': doc.employee,
						'attendance_date': from_date,
						'status': "Present",
						'company': frappe.db.get_value('Employee', doc.employee, 'company'),
						'shift': doc.shift,
					})
					attendance.flags.ignore_validate = True
					attendance.insert(ignore_permissions=True)
			finally:
				frappe.db.set_value("Employee Checkin", doc.name, 'attendance', attendance.name)
				to_process.append(attendance.name)
		from_date = add_to_date(from_date, days=1)

	for att in to_process:
		try:
			overtime = 0.00
			doc = frappe.get_doc("Attendance", att)
			logs = frappe.db.get_all("Employee Checkin", fields=["*"], filters=[
				["employee", "=", doc.employee],
				["time", "between", [doc.attendance_date, doc.attendance_date]],
			], order_by="time")

			total_working_hours = calculate_working_hours(
				logs,
				"Alternating entries as IN and OUT during the same shift",
				"Every Valid Check-in and Check-out",
			)[0]

			doc.flags.ignore_validate = True
			doc.working_hours = total_working_hours
			doc.processed = 1

			if frappe.db.get_value("Employee", doc.employee, "employment_type") == "Part-time":
				doc.status = "Present"
				doc.submit()
				continue

			if total_working_hours < 9.5:
				for log in logs:
					if log.shift:
						doc.late_entry = 1 if logs[0].time > log.shift_start else 0
						doc.early_exit = 1 if logs[-1].time < log.shift_end else 0
						break

			if total_working_hours >= 5:
				doc.status = "Present" if total_working_hours >= 7 else "Half Day"
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
				doc.submit()
			else:
				doc.status = "Absent"
				doc.save()
		except Exception as e:
			frappe.log_error(str(e), "Daily Attendance Marking Error - " + str(att))
			continue

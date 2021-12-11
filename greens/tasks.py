
# Copyright (c) 2021, Wahni Green Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import (
	flt,
	get_first_day,
	get_last_day,
	today,add_to_date,
	datetime,get_datetime,
	get_time_str,
	time_diff_in_hours,
)
from erpnext.hr.utils import (
	create_additional_leave_ledger_entry,
	get_leave_allocations
)
from erpnext.hr.doctype.employee_checkin.employee_checkin import (
	calculate_working_hours,
)


@frappe.whitelist()
def allocate_leave():
	today_date = today()
	month_start = get_first_day(today_date)
	leave_type = frappe.get_doc('Leave Type', 'Weekly Off')

	employee = [x.get('employee') for x in frappe.get_all("Attendance", filters = {
		"attendance_date": ["between", [month_start, today_date]],
		"docstatus": 1
	}, fields = ["DISTINCT(employee) as employee"])]

	for emp in employee:
		marked_days = frappe.get_all("Attendance", filters = {
			"attendance_date": ["between", [month_start, today_date]],
			"employee": emp,
			"docstatus": 1
		}, fields = ["COUNT(*) as marked_days"])[0].marked_days

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

	def half_day(doc, method=None):
	shift_checkout(doc)
		if doc.status == 'Half Day':
			logs = frappe.db.get_list('Employee Checkin', fields="*", filters={
				'skip_auto_attendance':'0',
				'employee': ['=',doc.employee],
				'time': ['>',today()],
				'time': ['<', add_to_date(today(), days=1, as_string=True)],
				}, order_by="employee,time")
				total_working_hours = calculate_working_hours(
				logs,
				'Strictly based on Log Type in Employee Checkin',
				'First Check-in and Last Check-out'
			)[0]
			if int(total_working_hours) < 5:
				frappe.throw('Not completed 5 Hours')

	def shift_checkout(doc):
		emp_details = frappe.get_all('Employee Checkin',filters={
			'employee': ['=',doc.employee],
			'time': ['>',today()],
			'time': ['<', add_to_date(today(), days=1, as_string=True)],
		},
		fields=['employee_name', 'employee','count(name) as count','log_type','time'],
		group_by="log_type",
		)
		total_in = 0
		total_out = 0
		for row in emp_details:
			if row.log_type=='IN':
				total_in = row.count
			if row.log_type=='OUT':
				total_out = row.count
			if str(total_in)>str(total_out):
				shift_detail = frappe.get_doc({
					'doctype': 'Employee Checkin',
					'employee': doc.employee,
					'log_type':'OUT',
					'time':today(),
					'employee_name': doc.employee_name
				})
				shift_detail.insert()

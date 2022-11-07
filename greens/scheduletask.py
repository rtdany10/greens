# Copyright (c) 2022, Wahni Green Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils.data import add_to_date, get_first_day, get_last_day, today
from frappe.query_builder.functions import Count
from pypika import CustomFunction
from pypika.functions import CurDate
from pypika.terms import Mod


def casual_leave_allocation():
	employees = frappe.qb.DocType('Employee')
	DateDiff = CustomFunction('DATEDIFF', ['start_date', 'end_date'])
	emp_data = (
		frappe.qb.from_(employees)
		.select(employees.employee)
		.where(employees.status == 'Active')
		.where((DateDiff(CurDate(), employees.date_of_joining) >= 365))
		.run(as_dict=True)
	)
	for emp in emp_data:
		allocation = frappe.get_doc(
			dict(
				doctype="Leave Allocation",
				employee=emp.employee,
				leave_type="Casual Leave",
				from_date=get_first_day(frappe.utils.today()),
				to_date=get_last_day(frappe.utils.today()),
				new_leaves_allocated=1,
			)
		)
		allocation.save(ignore_permissions=True)
		allocation.submit()


def auto_checkout_employee():
	employee_checkin = frappe.qb.DocType('Employee Checkin')
	DateDiff = CustomFunction('DATEDIFF', ['start_date', 'end_date'])
	emp_data = (
		frappe.qb.from_(employee_checkin)
		.select(employee_checkin.employee)
		.where(DateDiff(CurDate(), employee_checkin.time) == 0)
		.groupby(employee_checkin.employee)
		.having(
			Mod(Count(employee_checkin.name), 2) == 1
		)
	).run(as_dict=True)

	for emp in emp_data:
		frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": emp.employee,
			"time": add_to_date(today(), hours=22),
			"auto_checkout": 1
		}).insert(ignore_permissions=True)
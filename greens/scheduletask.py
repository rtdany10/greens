import frappe
from frappe import _
from frappe.utils import date_diff,getdate,today
from frappe.utils.data import get_last_day,get_first_day
from pypika.functions import DateDiff,CurDate

def casual_leave_allocation():
	employees = frappe.qb.DocType('Employee')
	emp_data = (
		frappe.qb.from_(employees)
			.select(employees.employee,employees.date_of_joining,employees.status)
			.where(employees.status == 'Active') 
			.where((DateDiff('day',CurDate(), employees.date_of_joining,alias=None) >= 365))
			).run(as_dict=True)
	for emp in emp_data:
		#date_of_joining = frappe.db.get_value("Employee", emp, "date_of_joining")
		#number_of_days = date_diff(frappe.utils.today(), date_of_joining)
		#if number_of_days >=365:
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

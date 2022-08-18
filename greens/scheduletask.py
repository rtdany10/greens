import frappe
from frappe.utils.data import get_first_day, get_last_day
from pypika import CustomFunction
from pypika.functions import CurDate


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

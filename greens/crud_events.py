# Copyright (c) 2022, Wahni Green Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import add_to_date
from erpnext.hr.doctype.employee_checkin.employee_checkin import calculate_working_hours
import copy


def calculate_emp_overtime(doc, method=None):
	if doc.working_hours >= 10.5:
		filters = {
			"skip_auto_attendance": 0,
			"attendance": ("is", "not set"),
			"time": ("between", (doc.in_time, doc.out_time)),
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
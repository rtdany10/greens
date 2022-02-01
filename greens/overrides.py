# Copyright (c) 2022, Wahni Green Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.hr.utils import get_holiday_dates_for_employee
from erpnext.payroll.doctype.salary_slip.salary_slip import SalarySlip
from frappe import _
from frappe.utils import (cint, date_diff, flt, format_date, getdate,
						  month_diff, today)


class CustomSalarySlip(SalarySlip):
	def before_insert(self):
		# super(SalarySlip, self).before_insert()
		self.custom_set_retirement()
		self.custom_set_holiday_working()
		self.custom_set_overtime()

	def get_working_days_details(self, joining_date=None, relieving_date=None, lwp=None, for_preview=0):
		payroll_based_on = frappe.db.get_value("Payroll Settings", None, "payroll_based_on")
		include_holidays_in_total_working_days = frappe.db.get_single_value("Payroll Settings", "include_holidays_in_total_working_days")

		working_days = date_diff(self.end_date, self.start_date) + 1
		if working_days > 30 or format_date(self.end_date, "MMMM") == "February":
			working_days = 30

		if for_preview:
			self.total_working_days = working_days
			self.payment_days = working_days
			return

		holidays = self.get_holidays_for_employee(self.start_date, self.end_date)

		if not cint(include_holidays_in_total_working_days):
			working_days -= len(holidays)
			if working_days < 0:
				frappe.throw(_("There are more holidays than working days this month."))

		if not payroll_based_on:
			frappe.throw(_("Please set Payroll based on in Payroll settings"))

		if payroll_based_on == "Attendance":
			actual_lwp, absent = self.calculate_lwp_ppl_and_absent_days_based_on_attendance(holidays)
			actual_lwp, absent = min(30, actual_lwp), min(30, absent)
			self.absent_days = absent
		else:
			actual_lwp = self.calculate_lwp_or_ppl_based_on_leave_application(holidays, working_days)
			actual_lwp = min(30, actual_lwp)

		if not lwp:
			lwp = actual_lwp
		elif lwp != actual_lwp:
			frappe.msgprint(_("Leave Without Pay does not match with approved {0} records").format(payroll_based_on))

		self.leave_without_pay = lwp
		self.total_working_days = working_days

		payment_days = self.get_payment_days(joining_date, relieving_date, include_holidays_in_total_working_days)

		if flt(payment_days) > flt(lwp):
			self.payment_days = flt(payment_days) - flt(lwp)

			if payroll_based_on == "Attendance":
				self.payment_days -= flt(absent)

			unmarked_days = self.get_unmarked_days()
			consider_unmarked_attendance_as = frappe.db.get_value("Payroll Settings", None, "consider_unmarked_attendance_as") or "Present"

			if payroll_based_on == "Attendance" and consider_unmarked_attendance_as == "Absent":
				self.absent_days += unmarked_days
				self.payment_days -= unmarked_days
				if include_holidays_in_total_working_days:
					for holiday in holidays:
						if not frappe.db.exists("Attendance", {"employee": self.employee, "attendance_date": holiday, "docstatus": 1}):
							self.payment_days += 1
		else:
			self.payment_days = 0

	def get_payment_days(self, joining_date, relieving_date, include_holidays_in_total_working_days):
		start_date, end_date = getdate(self.start_date), getdate(self.end_date)
		payment_days = date_diff(end_date, start_date) + 1
		if payment_days > 30 or format_date(self.end_date, "MMMM") == "February":
			payment_days = 30

		if not joining_date:
			joining_date, relieving_date = frappe.get_cached_value(
				"Employee", self.employee,
				["date_of_joining", "relieving_date"]
			)

		if joining_date:
			if start_date <= joining_date <= end_date:
				payment_days -= date_diff(joining_date, start_date)
			elif joining_date > end_date:
				return

		if relieving_date:
			if start_date <= relieving_date <= end_date:
				payment_days -= date_diff(end_date, relieving_date)
			elif relieving_date < start_date:
				frappe.throw(_("Employee relieved on {0} must be set as 'Left'").format(relieving_date))

		if not cint(include_holidays_in_total_working_days):
			holidays = self.get_holidays_for_employee(start_date, end_date)
			payment_days -= len(holidays)

		return payment_days

	def get_unmarked_days(self):
		unmarked_days = self.total_working_days
		joining_date, relieving_date = frappe.get_cached_value(
			"Employee", self.employee, ["date_of_joining", "relieving_date"]
		)

		if joining_date:
			if getdate(self.start_date) < joining_date <= getdate(self.end_date):
				unmarked_days -= date_diff(joining_date, self.start_date)

		if relieving_date:
			if getdate(self.start_date) <= relieving_date < getdate(self.end_date):
				unmarked_days -= date_diff(self.end_date, relieving_date)

		# self.total_working_days = unmarked_days
		frappe.msgprint(str(unmarked_days))
		unmarked_days -= frappe.get_all("Attendance", filters={
			"attendance_date": ["between", [self.start_date, self.end_date]],
			"employee": self.employee,
			"docstatus": 1
		}, fields=["COUNT(*) as marked_days"])[0].marked_days
		frappe.msgprint(str(unmarked_days))

		return unmarked_days

	def custom_set_retirement(self):
		retirement = frappe.db.get_value("Employee", self.employee, "date_of_retirement")
		if retirement and not month_diff(today(), retirement):
			self.is_retiring = 1

	def custom_set_holiday_working(self):
		holidays = get_holiday_dates_for_employee(self.employee, self.start_date, self.end_date)
		if not holidays:
			return

		holiday_working = 0
		attendance = frappe.get_all("Attendance", filters={
			"attendance_date": ["in", holidays],
			"docstatus": 1,
			"employee": self.employee,
			"status": ["in", ["Present", "Half Day"]]
		}, fields=["COUNT(name) as count", "status"], group_by="status")

		for d in attendance:
			if d["status"] == "Present":
				holiday_working += 1
			elif d["status"] == "Half Day":
				holiday_working += 0.5

		self.holiday_working = holiday_working

	def custom_set_overtime(self):
		overtime = frappe.get_all("Attendance", filters={
			"attendance_date": ["between", [self.start_date, self.end_date]],
			"docstatus": 1,
			"employee": self.employee,
		}, fields=["SUM(ot_below_ten) as overtime", "SUM(ot_above_ten) as overtime_after_ten"], group_by="employee")

		if not overtime:
			return
		self.overtime = overtime[0]["overtime"]
		self.ot_after_ten = overtime[0]["overtime_after_ten"]

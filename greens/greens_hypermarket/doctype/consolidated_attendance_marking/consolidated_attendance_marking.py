# Copyright (c) 2022, Wahni Green Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class ConsolidatedAttendanceMarking(Document):
	def before_insert(self):
		if self.attendance_date >= today():
			frappe.throw(_("Only allowed to process attendance till yesterday."))

		attendance = frappe.db.get_all('Attendance', filters={
			'attendance_date': self.attendance_date
		}, or_filters={
			'ot_above_ten': ['>', 0.00],
			'ot_below_ten': ['>', 0.00],
			'docstatus': 0
		}, pluck='name')

		if not attendance:
			frappe.throw(_("No attendance to process on the said date."))

		for att in attendance:
			self.append('attendance', {'attendance': att})

	def on_submit(self):
		for att in self.attendance:
			frappe.db.set_value('Attendance', att.attendance, {
				'working_hours': att.working_hours,
				'ot_below_ten': att.ot_before_10,
				'ot_above_ten': att.ot_after_10
			})
			if att.dstat == 0:
				doc = frappe.get_doc('Attendance', att.attendance)
				doc.status = att.status
				doc.submit()

	def on_cancel(self):
		frappe.throw(_("Processed attendance cannot be cancelled."))

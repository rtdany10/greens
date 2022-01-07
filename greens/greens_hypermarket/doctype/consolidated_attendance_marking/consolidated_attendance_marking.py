# Copyright (c) 2022, Wahni Green Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today
from frappe.model.document import Document

class ConsolidatedAttendanceMarking(Document):
	def before_insert(self):
		if self.attendance_date >= today():
			frappe.throw("Only allowed to process attendance till yesterday.")

		attendance = frappe.db.get_all('Attendance', filters={
			'workflow_state': 'Pending',
			'attendance_date': self.attendance_date
		}, pluck='name')

		if not attendance:
			frappe.throw("No attendance to process on the said date.")

		for att in attendance:
			self.append('attendance', {
				'attendance': att,
				'status': 'Approve'
			})

	def on_submit(self):
		for att in self.attendance:
			if att.status == 'Approve':
				frappe.get_doc('Attendance', att.attendance).submit()
			else:
				frappe.db.set_value('Attendance', att.attendance, 'workflow_state', 'Rejected')

	def on_cancel(self):
		frappe.throw("Processed attendance cannot be cancelled.")

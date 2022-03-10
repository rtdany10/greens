# Copyright (c) 2013, Wahni Green Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = []
	branch = [filters["branch"]] if filters.get("branch") else frappe.db.get_all("Branch", pluck="branch")

	for b in branch:
		records = frappe.db.get_all('Attendance', filters={
			"attendance_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
			"docstatus": 1,
			"branch": b
		}, fields=["count(name) as count", "status"], group_by="status")

		row = {
			"branch": b,
			"present": 0,
			"half_day": 0,
			"on_leave": 0,
			"absent": 0,
		}
		for record in records:
			row[str(record['status']).lower().replace(" ", "_")] = record['count']

		data.append(row)

	return columns, data


def get_columns():
	return [
		{
			"fieldname": "branch",
			"label": _("Branch"),
			"fieldtype": "Link",
			"options": "Branch",
			"width": 300
		},
		{
			"fieldname": "present",
			"label": _("Present"),
			"fieldtype": "Int",
			"default": 0
		},
		{
			"fieldname": "absent",
			"label": _("Absent"),
			"fieldtype": "Int",
			"default": 0
		},
		{
			"fieldname": "on_leave",
			"label": _("Leave"),
			"fieldtype": "Int",
			"default": 0
		},
		{
			"fieldname": "half_day",
			"label": _("Half Day"),
			"fieldtype": "Int",
			"default": 0
		},
	]

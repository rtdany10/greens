from . import __version__ as app_version

app_name = "greens"
app_title = "Greens Hypermarket"
app_publisher = "Wahni Green Technologies Pvt Ltd"
app_description = "Customizations for Greens Hypermarket"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "danyrt@wahni.com"
app_license = "GPL v3"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/greens/css/greens.css"
# app_include_js = "/assets/greens/js/greens.js"

# include js, css files in header of web template
# web_include_css = "/assets/greens/css/greens.css"
# web_include_js = "/assets/greens/js/greens.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "greens/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#    "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#     "methods": "greens.utils.jinja_methods",
#     "filters": "greens.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "greens.install.before_install"
# after_install = "greens.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "greens.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#     "Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#     "Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#     "ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events
doc_events = {
    "Attendance": {
        "on_submit": "greens.tasks.allocate_leave"
    },
    "Salary Slip": {
        "before_insert": "greens.tasks.salary_slip"
    },
    "Employee Checkin": {
        "before_insert": "greens.tasks.employee_checkout",
        "after_insert": "greens.tasks.link_attendance"
    }
}
# on_submit
# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily_long": [
        "greens.tasks.daily_attendance"
    ]
}

# Testing
# -------

# before_tests = "greens.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#     "frappe.desk.doctype.event.event.get_events": "greens.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#     "Task": "greens.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
#     {
#         "doctype": "{doctype_1}",
#         "filter_by": "{filter_by}",
#         "redact_fields": ["{field_1}", "{field_2}"],
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_2}",
#         "filter_by": "{filter_by}",
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_3}",
#         "strict": False,
#     },
#     {
#         "doctype": "{doctype_4}"
#     }
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#     "greens.auth.validate"
# ]

# Fixtures
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name", "in", [
                    "Salary Slip-holiday_working",
                    "Attendance-ot_below_ten",
                    "Attendance-ot_above_ten",
                    "Salary Slip-overtime",
                    "Salary Slip-ot_after_ten",
                    "Salary Slip-is_retiring"
                ]
            ]
        ]
    }
]

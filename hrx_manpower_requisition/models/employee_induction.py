from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MOD = 'hrx_manpower_requisition'
G_HR = f'{MOD}.group_hrx_hr'
G_CEO = f'{MOD}.group_hrx_ceo'

DEFAULT_HR_INDUCTION_ITEMS = [
    ("Company Introduction", "Overview of company history, vision, mission, and leadership.", "hr_induction"),
    ("Organizational Structure", "Explanation of company hierarchy and departments.", "hr_induction"),
    ("HR Policies", "Company rules, ethics, compliance and guidelines.", "hr_induction"),
    ("Attendance & Working Hours", "Check-in/out procedures, biometric / kiosk rules, late coming policy.", "hr_induction"),
    ("Leave Policy", "Paid leaves, sick leaves, casual leaves and approval process.", "hr_induction"),
    ("Dress Code & Code of Conduct", "Workplace decorum, dress code, harassment policy.", "hr_induction"),
    ("Communication Procedures", "Email etiquette, official channels, escalation matrix.", "hr_induction"),
]

DEFAULT_DEPT_INDUCTION_ITEMS = [
    ("Department Introduction", "Overview of department mission and team members.", "dept_induction"),
    ("Reporting Hierarchy", "Meeting reporting manager and immediate supervisors.", "dept_induction"),
    ("Role & Job Responsibilities", "Detailed job description and day-to-day duties.", "dept_induction"),
    ("Work Process & Workflows", "Standard operating procedures and approval chains.", "dept_induction"),
    ("Tools & Software Setup", "System access, logins, internal software and security credentials.", "dept_induction"),
    ("Department Targets & KRA/KPI", "Explanation of key performance indicators and expectations.", "dept_induction"),
]


class HrxEmployeeInduction(models.Model):
    _name = 'hrx.employee.induction'
    _description = 'Employee Induction & Training'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'employee_id, category, id'

    name = fields.Char('Topic / Checklist Item', required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True)
    category = fields.Selection([
        ('hr_induction', 'HR Induction'),
        ('dept_induction', 'Department Induction'),
        ('training', 'Role & Skills Training'),
    ], string='Category', required=True, default='hr_induction', tracking=True)
    description = fields.Text('Details / Instructions')
    responsible_id = fields.Many2one('res.users', string='Conducted By', default=lambda s: s.env.user)
    
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('waived', 'Waived'),
    ], default='pending', required=True, tracking=True)

    date_scheduled = fields.Date('Scheduled Date')
    completion_date = fields.Date('Completion Date', readonly=True)
    employee_acknowledged = fields.Boolean('Employee Acknowledged', readonly=True, copy=False)
    ack_date = fields.Datetime('Acknowledged On', readonly=True, copy=False)
    notes = fields.Text('Feedback / Notes')

    def action_start(self):
        for rec in self:
            rec.state = 'in_progress'

    def action_complete(self):
        for rec in self:
            rec.write({
                'state': 'completed',
                'completion_date': fields.Date.context_today(rec),
            })

    def action_waive(self):
        for rec in self:
            rec.state = 'waived'

    def action_employee_ack(self):
        for rec in self:
            if rec.employee_id.user_id.id != self.env.user.id and not self.env.user.has_group(G_HR):
                raise AccessError(_("Only the employee or HR can acknowledge this item."))
            rec.write({
                'employee_acknowledged': True,
                'ack_date': fields.Datetime.now(),
            })

    @api.model
    def create_default_induction(self, employee):
        """Populates default HR and Department induction items for an employee."""
        items = []
        existing_names = set(employee.hrx_induction_ids.mapped('name'))
        for name, desc, cat in DEFAULT_HR_INDUCTION_ITEMS:
            if name not in existing_names:
                items.append({
                    'name': name,
                    'employee_id': employee.id,
                    'category': cat,
                    'description': desc,
                    'responsible_id': self.env.uid,
                })
        for name, desc, cat in DEFAULT_DEPT_INDUCTION_ITEMS:
            if name not in existing_names:
                items.append({
                    'name': name,
                    'employee_id': employee.id,
                    'category': cat,
                    'description': desc,
                    'responsible_id': employee.parent_id.user_id.id or self.env.uid,
                })
        if items:
            self.create(items)

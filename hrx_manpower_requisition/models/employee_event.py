from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

HR_MANAGER = 'hr.group_hr_manager'

EVENT_TYPES = [
    ('joining', 'Joining'),
    ('probation_start', 'Probation Start'),
    ('probation_end', 'Probation End'),
    ('confirmation', 'Confirmation'),
    ('increment', 'Increment'),
    ('promotion', 'Promotion'),
    ('transfer', 'Department Transfer'),
    ('role_change', 'Role Change'),
    ('salary_revision', 'Salary Revision'),
    ('recognition', 'Recognition / Award'),
    ('warning', 'Warning / Disciplinary Action'),
    ('training', 'Training'),
    ('resignation', 'Resignation'),
    ('exit', 'Exit'),
]


class HrxEmployeeEvent(models.Model):
    _name = 'hrx.employee.event'
    _description = 'Employee Lifecycle Event'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', required=True, ondelete='cascade', index=True, tracking=True)
    department_id = fields.Many2one(
        'hr.department', related='employee_id.department_id', store=True, string='Department')
    company_id = fields.Many2one(
        'res.company', related='employee_id.company_id', store=True)
    event_type = fields.Selection(EVENT_TYPES, required=True, tracking=True)
    date = fields.Date('Effective Date', required=True,
                       default=fields.Date.context_today, tracking=True)
    date_to = fields.Date('Probation End Date')
    reason = fields.Text()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approval_date = fields.Datetime(readonly=True, copy=False)

    # Requested changes
    new_job_id = fields.Many2one('hr.job', string='New Position')
    new_department_id = fields.Many2one('hr.department', string='New Department')
    new_manager_id = fields.Many2one('hr.employee', string='New Reporting Manager')
    currency_id = fields.Many2one(
        'res.currency', related='employee_id.company_id.currency_id')
    new_salary = fields.Monetary('New Salary (Monthly)', currency_field='currency_id',
                                 groups=HR_MANAGER)

    # Values before the change (set when approved)
    old_job_id = fields.Many2one('hr.job', string='Previous Position', readonly=True, copy=False)
    old_department_id = fields.Many2one('hr.department', string='Previous Department',
                                        readonly=True, copy=False)
    old_manager_id = fields.Many2one('hr.employee', string='Previous Manager',
                                     readonly=True, copy=False)
    old_salary = fields.Monetary('Previous Salary', currency_field='currency_id',
                                 readonly=True, copy=False, groups=HR_MANAGER)

    # ------------------------------------------------------------------
    @api.depends('event_type', 'employee_id')
    def _compute_display_name(self):
        labels = dict(EVENT_TYPES)
        for rec in self:
            rec.display_name = "%s - %s" % (
                labels.get(rec.event_type, ''), rec.employee_id.name or '')

    @api.constrains('date', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date:
                raise ValidationError(_("The probation end date cannot be before the start date."))

    # ------------------------------------------------------------------
    def write(self, vals):
        if (not self.env.su and not self.env.context.get('hrx_wf')
                and any(rec.state == 'approved' for rec in self)):
            raise UserError(_("Approved events cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state == 'approved' for rec in self):
            raise UserError(_("Approved events cannot be deleted. Keep the history intact."))
        return super().unlink()

    # ------------------------------------------------------------------
    def _require_manager(self):
        if not (self.env.su or self.env.user.has_group(HR_MANAGER)):
            raise AccessError(_("Only an HR Manager can approve events."))

    def _validate_for_apply(self):
        self.ensure_one()
        t = self.event_type
        problems = {
            'probation_start': not self.date_to and _("Probation End Date"),
            'increment': not self.new_salary and _("New Salary"),
            'salary_revision': not self.new_salary and _("New Salary"),
            'transfer': not self.new_department_id and _("New Department"),
            'role_change': not self.new_job_id and _("New Position"),
            'promotion': not (self.new_job_id or self.new_salary) and _("New Position or New Salary"),
        }
        if problems.get(t):
            raise UserError(_("Please fill in: %s", problems[t]))

    def _apply_to_employee(self):
        self.ensure_one()
        emp = self.employee_id.sudo()
        old = {
            'old_job_id': emp.job_id.id,
            'old_department_id': emp.department_id.id,
            'old_manager_id': emp.parent_id.id,
            'old_salary': emp.hrx_salary,
        }
        vals = {}
        t = self.event_type
        if t in ('promotion', 'role_change') and self.new_job_id:
            vals['job_id'] = self.new_job_id.id
        if t == 'transfer':
            vals['department_id'] = self.new_department_id.id
            if self.new_manager_id:
                vals['parent_id'] = self.new_manager_id.id
        if t in ('increment', 'promotion', 'salary_revision') and self.new_salary:
            vals['hrx_salary'] = self.new_salary
        if t == 'probation_start':
            vals['hrx_probation_start'] = self.date
            vals['hrx_probation_end'] = self.date_to
        if t == 'probation_end':
            vals['hrx_probation_end'] = self.date
        if t == 'confirmation':
            vals['hrx_confirmation_date'] = self.date
        if vals:
            emp.write(vals)
        self.with_context(hrx_wf=True).write(dict(
            old, state='approved', approved_by=self.env.user.id,
            approval_date=fields.Datetime.now()))

    # ------------------------------------------------------------------
    def action_approve(self):
        self._require_manager()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft events can be approved."))
            rec._validate_for_apply()
        for rec in self:
            rec._apply_to_employee()

    def action_cancel(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft events can be cancelled."))
        self.with_context(hrx_wf=True).write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_("Only cancelled events can be reset to draft."))
        self.with_context(hrx_wf=True).write({'state': 'draft'})
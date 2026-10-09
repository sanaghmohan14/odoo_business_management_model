from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MOD = 'hrx_manpower_requisition'
G_HR = f'{MOD}.group_hrx_hr'
G_CEO = f'{MOD}.group_hrx_ceo'


class HrxHrTask(models.Model):
    _name = 'hrx.hr.task'
    _description = 'HR Task Planning & Execution'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_deadline asc, priority desc, id desc'

    name = fields.Char('Task Summary', required=True, tracking=True)
    task_type = fields.Selection([
        ('daily', 'Daily HR Task'),
        ('weekly', 'Weekly Task'),
        ('monthly', 'Monthly Task'),
        ('project', 'Project / Strategic Task'),
    ], string='Task Cadence', default='daily', required=True, tracking=True)

    assigned_to = fields.Many2one('res.users', string='Responsible Person', default=lambda s: s.env.user, tracking=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='1', tracking=True)

    date_deadline = fields.Date('Due Date', required=True, default=fields.Date.context_today, tracking=True)
    is_overdue = fields.Boolean('Overdue', compute='_compute_is_overdue', store=True)

    state = fields.Selection([
        ('created', 'Created'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('verified', 'Verified'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='created', required=True, tracking=True, copy=False)

    description = fields.Text('Task Details')
    remarks = fields.Text('Completion Remarks')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)

    @api.depends('date_deadline', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = (rec.date_deadline and rec.date_deadline < today and
                              rec.state not in ('verified', 'closed', 'cancelled'))

    def action_assign(self):
        for rec in self:
            rec.state = 'assigned'

    def action_start(self):
        for rec in self:
            rec.state = 'in_progress'

    def action_complete(self):
        for rec in self:
            rec.state = 'completed'

    def action_verify(self):
        for rec in self:
            rec.state = 'verified'

    def action_close(self):
        for rec in self:
            rec.state = 'closed'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

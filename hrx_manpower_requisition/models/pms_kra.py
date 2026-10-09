from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MOD = 'hrx_manpower_requisition'
G_HR = f'{MOD}.group_hrx_hr'
G_CEO = f'{MOD}.group_hrx_ceo'


class HrxPmsKra(models.Model):
    _name = 'hrx.pms.kra'
    _description = 'Performance Management - KRA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('KRA Title', required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True)
    manager_user_id = fields.Many2one('res.users', related='employee_id.parent_id.user_id', store=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True)

    period_start = fields.Date('Period Start', default=fields.Date.context_today)
    period_end = fields.Date('Period End')
    weightage = fields.Float('Weightage (%)', default=100.0)
    target_description = fields.Text('Objective & Key Results')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved by CEO'),
        ('in_progress', 'Active / In Progress'),
        ('reviewed', 'Reviewed'),
        ('closed', 'Closed'),
    ], default='draft', required=True, tracking=True, copy=False)

    kpi_ids = fields.One2many('hrx.pms.kpi', 'kra_id', string='KPIs')
    weekly_report_ids = fields.One2many('hrx.pms.weekly.report', 'kra_id', string='Weekly Reports')
    completion_rate = fields.Float('Overall Completion (%)', compute='_compute_completion_rate', store=True)

    monthly_rating = fields.Selection([
        ('1', '1 - Unsatisfactory'),
        ('2', '2 - Needs Improvement'),
        ('3', '3 - Meets Expectations'),
        ('4', '4 - Exceeds Expectations'),
        ('5', '5 - Outstanding'),
    ], string='Performance Assessment', tracking=True)
    performance_feedback = fields.Text('Review Feedback')
    improvement_plan = fields.Text('Improvement / Action Plan')

    @api.depends('weekly_report_ids.progress_percentage', 'kpi_ids.score')
    def _compute_completion_rate(self):
        for rec in self:
            if rec.weekly_report_ids:
                reports = rec.weekly_report_ids.filtered(lambda r: r.state in ('submitted', 'reviewed'))
                if reports:
                    rec.completion_rate = sum(reports.mapped('progress_percentage')) / len(reports)
                else:
                    rec.completion_rate = 0.0
            elif rec.kpi_ids:
                rec.completion_rate = sum(rec.kpi_ids.mapped('score')) / len(rec.kpi_ids)
            else:
                rec.completion_rate = 0.0

    def action_submit(self):
        for rec in self:
            rec.state = 'submitted'

    def action_approve(self):
        if not (self.env.su or self.env.user.has_group(G_CEO)):
            raise AccessError(_("Only the CEO can give final approval for KRAs."))
        for rec in self:
            rec.state = 'approved'

    def action_start(self):
        for rec in self:
            rec.state = 'in_progress'

    def action_review(self):
        for rec in self:
            rec.state = 'reviewed'

    def action_close(self):
        for rec in self:
            rec.state = 'closed'


class HrxPmsKpi(models.Model):
    _name = 'hrx.pms.kpi'
    _description = 'KRA Key Performance Indicator'

    kra_id = fields.Many2one('hrx.pms.kra', required=True, ondelete='cascade')
    name = fields.Char('KPI / Metric Name', required=True)
    target_value = fields.Float('Target Value', default=100.0)
    actual_value = fields.Float('Actual Value', default=0.0)
    uom = fields.Char('Unit of Measure', default='%')
    score = fields.Float('Score (%)', compute='_compute_score', store=True)

    @api.depends('target_value', 'actual_value')
    def _compute_score(self):
        for rec in self:
            if rec.target_value:
                rec.score = min((rec.actual_value / rec.target_value) * 100.0, 100.0)
            else:
                rec.score = 0.0


class HrxPmsWeeklyReport(models.Model):
    _name = 'hrx.pms.weekly.report'
    _description = 'Weekly KRA Progress Report'
    _order = 'week_start_date desc, id desc'

    kra_id = fields.Many2one('hrx.pms.kra', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', related='kra_id.employee_id', store=True)
    week_start_date = fields.Date('Week Start', required=True, default=fields.Date.context_today)
    week_end_date = fields.Date('Week End')
    progress_percentage = fields.Float('Progress Achieved (%)', default=0.0)
    achievements = fields.Text('Key Achievements This Week', required=True)
    challenges = fields.Text('Challenges / Blockers Encountered')
    plan_next_week = fields.Text('Plan for Next Week')
    manager_feedback = fields.Text('Reviewer / HR Feedback')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
    ], default='draft', required=True)

    def action_submit(self):
        for rec in self:
            rec.state = 'submitted'

    def action_review(self):
        for rec in self:
            rec.state = 'reviewed'

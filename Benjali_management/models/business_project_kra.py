from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BusinessProjectKRA(models.Model):
    _name = 'business.project.kra'
    _description = 'Business Project KRA'
    _order = 'sequence, id'

    name = fields.Char(string='KRA', required=True)
    reference = fields.Char(string='KRA Code', required=True, copy=False,
                            default='New', index=True)
    project_id = fields.Many2one('business.project', string='Business Project',
                                 required=True, ondelete='cascade', index=True)
    department_id = fields.Many2one('hr.department', string='Department',
                                    related='project_id.department_id', store=True,
                                    readonly=True, index=True)
    description = fields.Text(string='Description')
    objective = fields.Text(string='Objective')
    sequence = fields.Integer(string='Sequence', default=10)
    responsible_user_id = fields.Many2one('res.users', string='Responsible User',
                                          index=True)
    user_id = fields.Many2one('res.users', string='Assigned User',
                              related='responsible_user_id', store=True,
                              readonly=False, index=True)
    manager_id = fields.Many2one('res.users', string='Manager', index=True)
    kpi = fields.Char(string='KPI')
    target = fields.Float(string='Target', required=True, default=0.0)
    unit = fields.Char(string='Unit')
    measurement = fields.Char(string='Measurement')
    frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Frequency', default='daily', required=True)
    start_date = fields.Date(string='Start Date', default=fields.Date.context_today)
    end_date = fields.Date(string='End Date')
    state = fields.Selection([
        ('draft', 'Draft'), ('active', 'Active'), ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, index=True)
    priority = fields.Selection([
        ('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High'),
    ], string='Priority', default='0', index=True)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True,
                                 readonly=True, index=True)
    entry_ids = fields.One2many('business.project.kra.entry', 'kra_id',
                                string='KRA Entries', copy=False)
    employee_ids = fields.Many2many(
        'res.users', 'business_project_kra_employee_rel', 'kra_id', 'user_id',
        string='Assigned Employees',
        help='Employees whose work is measured by this KRA.')
    task_ids = fields.One2many('project.task', 'kra_id', string='Project Tasks')
    kpi_ids = fields.One2many('business.project.kpi', 'kra_id', string='KPI Definitions')
    entry_count = fields.Integer(compute='_compute_entry_count', string='Entries')
    task_count = fields.Integer(compute='_compute_task_metrics', string='Tasks')
    completed_task_count = fields.Integer(compute='_compute_task_metrics', string='Completed Tasks')
    pending_task_count = fields.Integer(compute='_compute_task_metrics', string='Pending Tasks')
    on_hold_task_count = fields.Integer(compute='_compute_task_metrics', string='On Hold Tasks')
    task_completion_percentage = fields.Float(
        compute='_compute_task_metrics', string='Task Completion (%)')
    achievement = fields.Float(compute='_compute_performance', string='Achievement',
                               store=True)
    progress_percentage = fields.Float(compute='_compute_performance',
                                       string='Progress (%)', store=True)
    kpi_weight_total = fields.Float(compute='_compute_kpi_score',
                                    string='Total KPI Weightage (%)', store=True)
    weighted_kpi_score = fields.Float(compute='_compute_kpi_score',
                                      string='Weighted KPI Score (%)', store=True)

    @api.depends('entry_ids')
    def _compute_entry_count(self):
        for kra in self:
            kra.entry_count = len(kra.entry_ids)

    @api.depends('task_ids.performance_status')
    def _compute_task_metrics(self):
        for kra in self:
            tasks = kra.task_ids
            kra.task_count = len(tasks)
            kra.completed_task_count = len(tasks.filtered(
                lambda task: task.performance_status == 'completed'))
            kra.pending_task_count = len(tasks.filtered(
                lambda task: task.performance_status in ('pending', 'in_progress')))
            kra.on_hold_task_count = len(tasks.filtered(
                lambda task: task.performance_status == 'on_hold'))
            kra.task_completion_percentage = (
                kra.completed_task_count / len(tasks) * 100 if tasks else 0.0)

    @api.depends('entry_ids.achievement', 'entry_ids.state', 'target',
                 'kpi_ids.performance_percentage', 'kpi_ids.weight')
    def _compute_performance(self):
        for kra in self:
            entries = kra.entry_ids.filtered(lambda entry: entry.state == 'approved')
            kra.achievement = sum(entries.mapped('achievement'))
            percentage = kra.achievement / kra.target * 100 if kra.target else 0.0
            kra.progress_percentage = (
                kra.weighted_kpi_score if kra.kpi_ids else
                min(max(percentage, 0.0), 100.0))

    @api.depends('kpi_ids.weight', 'kpi_ids.performance_percentage')
    def _compute_kpi_score(self):
        for kra in self:
            kra.kpi_weight_total = sum(kra.kpi_ids.mapped('weight'))
            kra.weighted_kpi_score = sum(
                kpi.performance_percentage * kpi.weight / 100
                for kpi in kra.kpi_ids)

    @api.constrains('target', 'start_date', 'end_date')
    def _check_kra_values(self):
        for kra in self:
            if kra.target < 0:
                raise ValidationError('KRA target cannot be negative.')
            if kra.end_date and kra.start_date and kra.end_date < kra.start_date:
                raise ValidationError('KRA end date must be on or after its start date.')

    def action_activate(self):
        self.write({'state': 'active', 'active': True})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled', 'active': False})

    def get_weekly_performance(self, date_from, date_to):
        self.ensure_one()
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        entries = self.entry_ids.filtered(
            lambda entry: entry.state == 'approved' and date_from <= entry.date <= date_to)
        return sum(entries.mapped('achievement')) / self.target * 100 if self.target else 0.0

    def get_monthly_performance(self, date_from, date_to):
        return self.get_weekly_performance(date_from, date_to)


class BusinessProjectKPI(models.Model):
    _name = 'business.project.kpi'
    _description = 'Business Project KPI'
    _order = 'kra_id, sequence, id'

    name = fields.Char(string='KPI', required=True)
    code = fields.Char(string='KPI Code', copy=False)
    kra_id = fields.Many2one('business.project.kra', string='KRA', required=True,
                             ondelete='cascade', index=True)
    project_id = fields.Many2one(related='kra_id.project_id', store=True,
                                 string='Business Project', readonly=True, index=True)
    department_id = fields.Many2one(related='kra_id.department_id', store=True,
                                    string='Department', readonly=True, index=True)
    employee_id = fields.Many2one('res.users', string='Measured Employee', required=True,
                                  index=True)
    description = fields.Text(string='Definition')
    measurement_type = fields.Selection([
        ('quantity', 'Quantity'), ('percentage', 'Percentage'),
        ('quality', 'Quality Score'), ('timeliness', 'Timeliness'),
    ], string='Measurement Type', required=True, default='quantity')
    target = fields.Float(string='Target', required=True, default=0.0)
    unit = fields.Char(string='Unit', required=True, default='points')
    weight = fields.Float(string='Weightage (%)', default=0.0,
                          help='Importance of this KPI in the total KRA score. For example, 40 means 40%.')
    frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Measurement Frequency', required=True, default='daily')
    start_date = fields.Date(related='kra_id.start_date', store=True, readonly=True)
    end_date = fields.Date(related='kra_id.end_date', store=True, readonly=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    entry_ids = fields.One2many('business.project.kra.entry', 'kpi_id', string='Performance Entries')
    entry_count = fields.Integer(compute='_compute_entry_count', string='Entries')
    achievement = fields.Float(compute='_compute_performance', string='Achievement', store=True)
    performance_percentage = fields.Float(compute='_compute_performance', string='Performance (%)', store=True)
    weighted_contribution = fields.Float(compute='_compute_weighted_contribution',
                                         string='Weighted Contribution (%)', store=True)

    @api.depends('entry_ids')
    def _compute_entry_count(self):
        for kpi in self:
            kpi.entry_count = len(kpi.entry_ids)

    @api.depends('entry_ids.achievement', 'entry_ids.state', 'target')
    def _compute_performance(self):
        for kpi in self:
            entries = kpi.entry_ids.filtered(lambda entry: entry.state == 'approved')
            kpi.achievement = sum(entries.mapped('achievement'))
            score = kpi.achievement / kpi.target * 100 if kpi.target else 0.0
            kpi.performance_percentage = min(max(score, 0.0), 100.0)

    @api.depends('performance_percentage', 'weight')
    def _compute_weighted_contribution(self):
        for kpi in self:
            kpi.weighted_contribution = kpi.performance_percentage * kpi.weight / 100

    @api.constrains('target', 'weight')
    def _check_kpi_values(self):
        for kpi in self:
            if kpi.target < 0:
                raise ValidationError('KPI target cannot be negative.')
            if kpi.weight < 0 or kpi.weight > 100:
                raise ValidationError('KPI weightage must be between 0 and 100.')
            total_weight = sum(kpi.kra_id.kpi_ids.mapped('weight'))
            if total_weight > 100:
                raise ValidationError(
                    'The total KPI weightage for a KRA cannot exceed 100%%. '
                    'Current total: %.2f%%.' % total_weight)







class BusinessProjectKRAEntry(models.Model):
    _name = 'business.project.kra.entry'
    _description = 'Business Project KRA Entry'
    _order = 'date desc, id desc'

    name = fields.Char(string='Work Summary', required=True)
    kra_id = fields.Many2one('business.project.kra', string='KRA', required=True,
                             ondelete='cascade', index=True)
    kpi_id = fields.Many2one('business.project.kpi', string='KPI',
                             ondelete='cascade', index=True)
    task_id = fields.Many2one('project.task', string='Project Task',
                              ondelete='cascade', index=True)
    project_id = fields.Many2one(related='kra_id.project_id', store=True,
                                 string='Business Project', readonly=True, index=True)
    department_id = fields.Many2one(related='kra_id.department_id', store=True,
                                    string='Department', readonly=True, index=True)
    employee_id = fields.Many2one('res.users', string='Assigned Employee', required=True,
                                  index=True)
    user_id = fields.Many2one(related='employee_id', store=True,
                              string='Employee', readonly=True, index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today,
                       index=True)
    day = fields.Selection([
        ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
        ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
    ], string='Day', compute='_compute_period', store=True)
    week_start = fields.Date(string='Week', compute='_compute_period', store=True,
                             index=True)
    month_start = fields.Date(string='Month', compute='_compute_period', store=True,
                              index=True)
    period_type = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Performance Period', required=True, default='daily', index=True)
    target = fields.Float(string='Target', required=True, default=0.0)
    achievement = fields.Float(string='Actual Achievement', required=True, default=0.0)
    frequency = fields.Selection(related='kra_id.frequency', store=True,
                                 string='Frequency', readonly=True, index=True)
    progress_percentage = fields.Float(string='Progress (%)',
                                       compute='_compute_percentage', store=True)
    unit = fields.Char(string='Unit', default='points')
    task_status = fields.Selection([
        ('pending', 'Pending'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'), ('on_hold', 'On Hold'),
        ('blocked', 'Blocked'), ('cancelled', 'Cancelled'),
    ], string='Task Status', required=True, default='pending', index=True)
    completion_date = fields.Date(string='Completion Date')
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Submitted'),
        ('approved', 'Approved'), ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, index=True)
    company_id = fields.Many2one(related='kra_id.company_id', store=True,
                                 readonly=True, index=True)

    @api.depends('date')
    def _compute_period(self):
        for entry in self:
            date = fields.Date.to_date(entry.date)
            entry.day = str(date.weekday()) if date else False
            entry.week_start = date - timedelta(days=date.weekday()) if date else False
            entry.month_start = date.replace(day=1) if date else False

    @api.depends('achievement', 'target')
    def _compute_percentage(self):
        for entry in self:
            percentage = entry.achievement / entry.target * 100 if entry.target else 0.0
            entry.progress_percentage = min(max(percentage, 0.0), 100.0)

    @api.constrains('achievement', 'target', 'date', 'completion_date')
    def _check_entry_values(self):
        for entry in self:
            if entry.achievement < 0 or entry.target < 0:
                raise ValidationError('Target and achievement cannot be negative.')
            if entry.completion_date and entry.completion_date < entry.date:
                raise ValidationError('Completion date cannot be before the performance date.')

    @api.onchange('kpi_id')
    def _onchange_kpi_id(self):
        for entry in self:
            if entry.kpi_id:
                entry.kra_id = entry.kpi_id.kra_id
                entry.employee_id = entry.kpi_id.employee_id
                entry.target = entry.kpi_id.target
                entry.unit = entry.kpi_id.unit
                entry.period_type = entry.kpi_id.frequency

    @api.onchange('task_id')
    def _onchange_task_id(self):
        for entry in self:
            if entry.task_id:
                entry.kra_id = entry.task_id.kra_id
                if entry.task_id.assigned_employee_id:
                    entry.employee_id = entry.task_id.assigned_employee_id

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BusinessProjectKRA(models.Model):
    _name = 'business.project.kra'
    _description = 'Business Project & Department KRA'
    _order = 'sequence, id'

    name = fields.Char(string='KRA Name', required=True)
    reference = fields.Char(string='KRA Code', required=True, copy=False,
                            default='New', index=True)

    # Department is primary: can be a Department KRA or Project KRA
    department_id = fields.Many2one(
        'hr.department', string='Department', required=True, index=True,
        default=lambda self: self._default_department_id(),
        help='Department responsible for this Key Result Area.')
    project_id = fields.Many2one(
        'business.project', string='Business Project', required=False,
        ondelete='set null', index=True,
        domain="[('department_id', '=', department_id)]",
        help='Optional: specify a project if this KRA is project-specific. Leave empty for Department-level KRA.')

    description = fields.Text(string='Description')
    objective = fields.Text(string='Strategic Objective')
    sequence = fields.Integer(string='Sequence', default=10)

    responsible_user_id = fields.Many2one(
        'res.users', string='Responsible User / Lead', index=True,
        default=lambda self: self.env.user)
    user_id = fields.Many2one(
        'res.users', string='Assigned User',
        related='responsible_user_id', store=True, readonly=False, index=True)
    manager_id = fields.Many2one('res.users', string='Reviewing Manager', index=True)

    # Direct target & KPI summary (used when no detailed sub-KPIs are defined)
    kpi = fields.Char(string='KPI Summary')
    measurement = fields.Char(string='Measurement Method')
    target = fields.Float(string='Target', required=True, default=0.0)
    unit = fields.Char(string='Unit', default='units', help='e.g. units, %, hours, leads, students, etc.')
    frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Frequency', default='monthly', required=True)

    start_date = fields.Date(string='Start Date', default=fields.Date.context_today)
    end_date = fields.Date(string='End Date')

    state = fields.Selection([
        ('draft', 'Draft'), ('active', 'Active'), ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, index=True)
    priority = fields.Selection([
        ('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High'),
    ], string='Priority', default='1', index=True)
    active = fields.Boolean(string='Active', default=True)

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True)

    # Related items
    entry_ids = fields.One2many(
        'business.project.kra.entry', 'kra_id', string='Performance Entries', copy=False)
    employee_ids = fields.Many2many(
        'res.users', 'business_project_kra_employee_rel', 'kra_id', 'user_id',
        string='Assigned Employees',
        help='Employees whose work is measured by this KRA.')
    task_ids = fields.One2many('project.task', 'kra_id', string='Project Tasks')
    kpi_ids = fields.One2many(
        'business.project.kpi', 'kra_id', string='KPI Definitions')

    # Metrics
    kpi_count = fields.Integer(compute='_compute_kpi_count', string='KPIs')
    entry_count = fields.Integer(compute='_compute_entry_count', string='Entries')
    task_count = fields.Integer(compute='_compute_task_metrics', string='Tasks')
    completed_task_count = fields.Integer(compute='_compute_task_metrics', string='Completed Tasks')
    pending_task_count = fields.Integer(compute='_compute_task_metrics', string='Pending Tasks')
    on_hold_task_count = fields.Integer(compute='_compute_task_metrics', string='On Hold Tasks')
    task_completion_percentage = fields.Float(
        compute='_compute_task_metrics', string='Task Completion (%)')

    achievement = fields.Float(compute='_compute_performance', string='Actual Achievement', store=True)
    progress_percentage = fields.Float(compute='_compute_performance', string='Progress (%)', store=True)
    kpi_weight_total = fields.Float(compute='_compute_kpi_score', string='Total KPI Weight (%)', store=True)
    weighted_kpi_score = fields.Float(compute='_compute_kpi_score', string='Weighted KPI Score (%)', store=True)

    def _default_department_id(self):
        ctx_dept = self.env.context.get('default_department_id')
        if ctx_dept:
            return ctx_dept
        user_dept = self.env.user.department_id.id if hasattr(self.env.user, 'department_id') and self.env.user.department_id else False
        return user_dept or False

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.project_id.department_id:
            self.department_id = self.project_id.department_id

    @api.onchange('department_id')
    def _onchange_department_id(self):
        if self.project_id and self.department_id and self.project_id.department_id != self.department_id:
            self.project_id = False

    @api.depends('kpi_ids')
    def _compute_kpi_count(self):
        for kra in self:
            kra.kpi_count = len(kra.kpi_ids)

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
                 'weighted_kpi_score', 'kpi_ids')
    def _compute_performance(self):
        for kra in self:
            entries = kra.entry_ids.filtered(lambda entry: entry.state == 'approved')
            kra.achievement = sum(entries.mapped('achievement'))
            if kra.kpi_ids:
                # When KPI definitions exist, KRA progress is weighted score of its KPIs
                kra.progress_percentage = kra.weighted_kpi_score
            else:
                # Direct KRA calculation
                percentage = (kra.achievement / kra.target * 100) if kra.target else 0.0
                kra.progress_percentage = min(max(percentage, 0.0), 100.0)

    @api.depends('kpi_ids.weight', 'kpi_ids.performance_percentage')
    def _compute_kpi_score(self):
        for kra in self:
            kra.kpi_weight_total = sum(kra.kpi_ids.mapped('weight'))
            total_weight = kra.kpi_weight_total or 100.0
            kra.weighted_kpi_score = sum(
                kpi.performance_percentage * (kpi.weight / total_weight)
                for kpi in kra.kpi_ids
            ) if kra.kpi_ids else 0.0

    @api.constrains('target', 'start_date', 'end_date')
    def _check_kra_values(self):
        for kra in self:
            if kra.target < 0:
                raise ValidationError('KRA target cannot be negative.')
            if kra.end_date and kra.start_date and kra.end_date < kra.start_date:
                raise ValidationError('KRA end date must be on or after its start date.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference') or vals.get('reference') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('business.project.kra') or 'KRA'
        return super().create(vals_list)

    def action_activate(self):
        self.write({'state': 'active', 'active': True})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled', 'active': False})

    def action_view_kpis(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - KPIs',
            'res_model': 'business.project.kpi',
            'view_mode': 'list,form',
            'domain': [('kra_id', '=', self.id)],
            'context': {
                'default_kra_id': self.id,
                'default_department_id': self.department_id.id,
                'default_project_id': self.project_id.id if self.project_id else False,
            },
        }

    def action_view_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Performance Entries',
            'res_model': 'business.project.kra.entry',
            'view_mode': 'list,kanban,form,pivot,graph',
            'domain': [('kra_id', '=', self.id)],
            'context': {
                'default_kra_id': self.id,
                'default_department_id': self.department_id.id,
                'default_project_id': self.project_id.id if self.project_id else False,
            },
        }


class BusinessProjectKPI(models.Model):
    _name = 'business.project.kpi'
    _description = 'Business Project & Department KPI'
    _order = 'kra_id, sequence, id'

    name = fields.Char(string='KPI Name', required=True)
    code = fields.Char(string='KPI Code', copy=False, default='New')
    kra_id = fields.Many2one('business.project.kra', string='KRA', required=True,
                             ondelete='cascade', index=True)

    department_id = fields.Many2one(
        'hr.department', string='Department', related='kra_id.department_id',
        store=True, readonly=True, index=True)
    project_id = fields.Many2one(
        'business.project', string='Business Project', related='kra_id.project_id',
        store=True, readonly=True, index=True)

    employee_id = fields.Many2one(
        'res.users', string='Measured Owner / Employee', required=False,
        default=lambda self: self.env.user, index=True)
    description = fields.Text(string='Measurement Description')

    measurement_type = fields.Selection([
        ('quantity', 'Quantity / Count'),
        ('percentage', 'Percentage (%)'),
        ('quality', 'Quality Score (Rating)'),
        ('timeliness', 'Timeliness (Hours/Days)'),
    ], string='Measurement Type', required=True, default='quantity')

    target = fields.Float(string='Target', required=True, default=0.0)
    unit = fields.Char(string='Unit', required=True, default='units')
    weight = fields.Float(string='Weightage (%)', default=100.0,
                          help='Importance of this KPI in the parent KRA score (e.g. 50%).')
    frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Frequency', required=True, default='monthly')

    start_date = fields.Date(related='kra_id.start_date', store=True, readonly=True)
    end_date = fields.Date(related='kra_id.end_date', store=True, readonly=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    entry_ids = fields.One2many(
        'business.project.kra.entry', 'kpi_id', string='Performance Entries')
    entry_count = fields.Integer(compute='_compute_entry_count', string='Entries')

    achievement = fields.Float(compute='_compute_performance', string='Actual Achievement', store=True)
    performance_percentage = fields.Float(compute='_compute_performance', string='Performance (%)', store=True)
    weighted_contribution = fields.Float(compute='_compute_weighted_contribution',
                                         string='Contribution to KRA (%)', store=True)

    @api.onchange('kra_id')
    def _onchange_kra_id(self):
        if self.kra_id:
            if not self.employee_id and self.kra_id.responsible_user_id:
                self.employee_id = self.kra_id.responsible_user_id
            if self.unit == 'units' and self.kra_id.unit:
                self.unit = self.kra_id.unit
            if self.kra_id.frequency:
                self.frequency = self.kra_id.frequency

    @api.depends('entry_ids')
    def _compute_entry_count(self):
        for kpi in self:
            kpi.entry_count = len(kpi.entry_ids)

    @api.depends('entry_ids.achievement', 'entry_ids.state', 'target')
    def _compute_performance(self):
        for kpi in self:
            entries = kpi.entry_ids.filtered(lambda entry: entry.state == 'approved')
            kpi.achievement = sum(entries.mapped('achievement'))
            score = (kpi.achievement / kpi.target * 100) if kpi.target else 0.0
            kpi.performance_percentage = min(max(score, 0.0), 100.0)

    @api.depends('performance_percentage', 'weight')
    def _compute_weighted_contribution(self):
        for kpi in self:
            kpi.weighted_contribution = (kpi.performance_percentage * kpi.weight / 100.0)

    @api.constrains('target', 'weight')
    def _check_kpi_values(self):
        for kpi in self:
            if kpi.target < 0:
                raise ValidationError('KPI target cannot be negative.')
            if kpi.weight < 0 or kpi.weight > 100:
                raise ValidationError('KPI weightage must be between 0 and 100.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals.get('code') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('business.project.kpi') or 'KPI'
        return super().create(vals_list)

    def action_view_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Entries',
            'res_model': 'business.project.kra.entry',
            'view_mode': 'list,form',
            'domain': [('kpi_id', '=', self.id)],
            'context': {
                'default_kpi_id': self.id,
                'default_kra_id': self.kra_id.id,
                'default_department_id': self.department_id.id,
                'default_employee_id': self.employee_id.id if self.employee_id else self.env.user.id,
                'default_target': self.target,
                'default_unit': self.unit,
                'default_period_type': self.frequency,
            },
        }


class BusinessProjectKRAEntry(models.Model):
    _name = 'business.project.kra.entry'
    _description = 'Performance Entry Log'
    _order = 'date desc, id desc'

    name = fields.Char(string='Work / Achievement Summary', required=True)
    kra_id = fields.Many2one(
        'business.project.kra', string='KRA', required=True,
        ondelete='cascade', index=True)
    kpi_id = fields.Many2one(
        'business.project.kpi', string='KPI (Optional)',
        ondelete='cascade', index=True, domain="[('kra_id', '=', kra_id)]")
    task_id = fields.Many2one(
        'project.task', string='Project Task',
        ondelete='cascade', index=True)

    department_id = fields.Many2one(
        'hr.department', string='Department', compute='_compute_hierarchy',
        store=True, readonly=False, index=True)
    project_id = fields.Many2one(
        'business.project', string='Business Project', compute='_compute_hierarchy',
        store=True, readonly=False, index=True)

    employee_id = fields.Many2one(
        'res.users', string='Employee / Contributor', required=True,
        default=lambda self: self.env.user, index=True)
    user_id = fields.Many2one(
        'res.users', string='Employee Link', related='employee_id',
        store=True, readonly=True, index=True)

    date = fields.Date(
        string='Date', required=True, default=fields.Date.context_today,
        index=True)
    day = fields.Selection([
        ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
        ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
    ], string='Day', compute='_compute_period', store=True)
    week_start = fields.Date(
        string='Week', compute='_compute_period', store=True, index=True)
    month_start = fields.Date(
        string='Month', compute='_compute_period', store=True, index=True)

    period_type = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
    ], string='Performance Period', required=True, default='monthly', index=True)

    target = fields.Float(string='Target for Period', required=True, default=0.0)
    achievement = fields.Float(string='Actual Achievement', required=True, default=0.0)
    progress_percentage = fields.Float(
        string='Progress (%)', compute='_compute_percentage', store=True)
    unit = fields.Char(string='Unit', default='units')

    task_status = fields.Selection([
        ('pending', 'Pending'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'), ('on_hold', 'On Hold'),
        ('blocked', 'Blocked'), ('cancelled', 'Cancelled'),
    ], string='Task Status', required=True, default='completed', index=True)
    completion_date = fields.Date(string='Completion Date')
    notes = fields.Text(string='Notes / Justification')

    state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Submitted'),
        ('approved', 'Approved'), ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, index=True,
       help='Approved entries contribute to KPI and KRA progress.')

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True)

    @api.depends('kra_id', 'kpi_id')
    def _compute_hierarchy(self):
        for entry in self:
            if entry.kpi_id:
                entry.department_id = entry.kpi_id.department_id
                entry.project_id = entry.kpi_id.project_id
            elif entry.kra_id:
                entry.department_id = entry.kra_id.department_id
                entry.project_id = entry.kra_id.project_id

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
            percentage = (entry.achievement / entry.target * 100) if entry.target else 0.0
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
        if self.kpi_id:
            self.kra_id = self.kpi_id.kra_id
            self.department_id = self.kpi_id.department_id
            self.project_id = self.kpi_id.project_id
            self.target = self.kpi_id.target
            self.unit = self.kpi_id.unit
            self.period_type = self.kpi_id.frequency
            if self.kpi_id.employee_id:
                self.employee_id = self.kpi_id.employee_id

    @api.onchange('kra_id')
    def _onchange_kra_id(self):
        if self.kra_id:
            self.department_id = self.kra_id.department_id
            self.project_id = self.kra_id.project_id
            if not self.kpi_id:
                self.target = self.kra_id.target
                self.unit = self.kra_id.unit
                self.period_type = self.kra_id.frequency
                if self.kra_id.responsible_user_id:
                    self.employee_id = self.kra_id.responsible_user_id

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id and self.task_id.kra_id:
            self.kra_id = self.task_id.kra_id
            if self.task_id.assigned_employee_id:
                self.employee_id = self.task_id.assigned_employee_id

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})

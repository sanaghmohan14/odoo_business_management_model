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
    entry_count = fields.Integer(compute='_compute_entry_count', string='Entries')
    achievement = fields.Float(compute='_compute_performance', string='Achievement',
                               store=True)
    progress_percentage = fields.Float(compute='_compute_performance',
                                       string='Progress (%)', store=True)

    @api.depends('entry_ids')
    def _compute_entry_count(self):
        for kra in self:
            kra.entry_count = len(kra.entry_ids)

    @api.depends('entry_ids.achievement', 'target')
    def _compute_performance(self):
        for kra in self:
            kra.achievement = sum(kra.entry_ids.mapped('achievement'))
            percentage = kra.achievement / kra.target * 100 if kra.target else 0.0
            kra.progress_percentage = min(max(percentage, 0.0), 100.0)

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
        entries = self.entry_ids.filtered(lambda entry: date_from <= entry.date <= date_to)
        return sum(entries.mapped('achievement')) / self.target * 100 if self.target else 0.0

    def get_monthly_performance(self, date_from, date_to):
        return self.get_weekly_performance(date_from, date_to)







class BusinessProjectKRAEntry(models.Model):
    _name = 'business.project.kra.entry'
    _description = 'Business Project KRA Entry'
    _order = 'date desc, id desc'

    name = fields.Char(string='Description')
    kra_id = fields.Many2one('business.project.kra', string='KRA', required=True,
                             ondelete='cascade', index=True)
    project_id = fields.Many2one(related='kra_id.project_id', store=True,
                                 string='Business Project', readonly=True, index=True)
    department_id = fields.Many2one(related='kra_id.department_id', store=True,
                                    string='Department', readonly=True, index=True)
    user_id = fields.Many2one(related='kra_id.user_id', store=True,
                              string='Responsible User', readonly=True, index=True)
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
    target = fields.Float(related='kra_id.target', readonly=True)
    achievement = fields.Float(string='Achievement', required=True, default=0.0)
    frequency = fields.Selection(related='kra_id.frequency', store=True,
                                 string='Frequency', readonly=True, index=True)
    progress_percentage = fields.Float(string='Progress (%)',
                                       compute='_compute_percentage', store=True)
    unit = fields.Char(related='kra_id.unit', readonly=True)
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

    @api.constrains('achievement')
    def _check_achievement(self):
        if any(entry.achievement < 0 for entry in self):
            raise ValidationError('Achievement cannot be negative.')

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})

from datetime import timedelta
from odoo import api, fields, models


class BusinessReportingWizard(models.TransientModel):
    _name = 'business.reporting.wizard'
    _description = 'Business Reporting Wizard'

    report_type = fields.Selection([
        ('all', 'Comprehensive KRA & KPI Report'),
        ('daily', 'Daily Report (Today / Selected Date)'),
        ('weekly', 'Weekly Report (Targets & Achievements)'),
        ('monthly', 'Monthly Report (Target: 100 Score)'),
    ], string='Report Type', default='all', required=True)

    date = fields.Date(string='Report Date', default=fields.Date.context_today)
    start_date = fields.Date(string='Start Date', default=fields.Date.context_today)
    end_date = fields.Date(string='End Date')

    project_id = fields.Many2one('business.project', string='Business Project')
    kra_id = fields.Many2one('business.project.kra', string='Key Result Area (KRA)')
    department_id = fields.Many2one('hr.department', string='Department')
    employee_id = fields.Many2one('res.users', string='Assigned Employee')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            if self.project_id.department_id:
                self.department_id = self.project_id.department_id
            return {'domain': {'kra_id': [('project_id', '=', self.project_id.id)]}}
        return {'domain': {'kra_id': []}}

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('Benjali_management.action_kra_kpi_performance_report').report_action(self)

    def action_view_analysis(self):
        self.ensure_one()
        domain = []
        if self.project_id:
            domain.append(('project_id', '=', self.project_id.id))
        if self.kra_id:
            domain.append(('kra_id', '=', self.kra_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))

        if self.report_type == 'daily':
            if self.date:
                domain.append(('date', '=', self.date))
            action = self.env.ref('Benjali_management.business_project_daily_report_action').read()[0]
        elif self.report_type == 'weekly':
            if self.start_date:
                domain.append(('date', '>=', self.start_date))
            if self.end_date:
                domain.append(('date', '<=', self.end_date))
            action = self.env.ref('Benjali_management.business_project_weekly_report_action').read()[0]
        elif self.report_type == 'monthly':
            if self.start_date:
                domain.append(('date', '>=', self.start_date))
            if self.end_date:
                domain.append(('date', '<=', self.end_date))
            action = self.env.ref('Benjali_management.business_project_monthly_report_action').read()[0]
        else:
            action = self.env.ref('Benjali_management.business_project_kpi_action').read()[0]

        action['domain'] = domain
        return action

    def action_print_xlsx(self):
        # Fallback to pdf report action if xlsx generator is not configured
        return self.action_print_report()
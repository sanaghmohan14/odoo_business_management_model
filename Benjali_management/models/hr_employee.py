from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    kpi_count = fields.Integer(
        string='KPIs Count',
        compute='_compute_kpi_count',
        help='Number of active KPIs assigned to this employee.',
    )

    def _compute_kpi_count(self):
        KPI = self.env['business.project.kpi']
        for emp in self:
            if not emp.id or not emp.user_id:
                emp.kpi_count = 0
                continue
            emp.kpi_count = KPI.search_count([
                '|',
                ('employee_ids', 'in', [emp.user_id.id]),
                ('employee_id', '=', emp.user_id.id),
            ])

    def action_view_kpis(self):
        self.ensure_one()
        user_id = self.user_id.id if self.user_id else None
        domain = [
            '|',
            ('employee_ids', 'in', [user_id]),
            ('employee_id', '=', user_id),
        ] if user_id else [('id', '=', 0)]
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Assigned KPIs',
            'res_model': 'business.project.kpi',
            'view_mode': 'kanban,list,form,pivot,graph',
            'domain': domain,
            'context': {
                'default_employee_ids': [(4, user_id)] if user_id else [],
                'search_default_group_stage_id': 1,
            },
            'target': 'current',
        }

from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    kpi_count = fields.Integer(
        string='KPIs Count',
        compute='_compute_kpi_count',
        search='_search_kpi_count',
        help='Number of active KPIs assigned to this employee.',
    )

    def _get_assigned_kpi_domain(self):
        self.ensure_one()
        user_id = self.user_id.id if self.user_id else False
        emp_id = self.id
        if user_id and emp_id:
            return ['|', ('employee_ids', 'in', [user_id]), ('hr_employee_ids', 'in', [emp_id])]
        elif user_id:
            return [('employee_ids', 'in', [user_id])]
        elif emp_id:
            return [('hr_employee_ids', 'in', [emp_id])]
        return [('id', '=', False)]

    def _compute_kpi_count(self):
        KPI = self.env['business.project.kpi']
        for emp in self:
            if not emp.id:
                emp.kpi_count = 0
                continue
            domain = emp._get_assigned_kpi_domain()
            emp.kpi_count = KPI.search_count(domain)

    def _search_kpi_count(self, operator, value):
        KPI = self.env['business.project.kpi']
        all_kpis = KPI.search([])
        assigned_user_ids = all_kpis.mapped('employee_ids.id')
        assigned_emp_ids = all_kpis.mapped('hr_employee_ids.id')

        domain = ['|', ('user_id', 'in', assigned_user_ids), ('id', 'in', assigned_emp_ids)]
        if (operator in ('>', '>=') and value > 0) or (operator == '!=' and value == 0):
            return domain
        elif (operator == '=' and value == 0) or (operator in ('<=', '<') and value <= 0):
            return ['!', '&'] + domain
        return []

    def action_view_kpis(self):
        self.ensure_one()
        domain = self._get_assigned_kpi_domain()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Assigned KPIs',
            'res_model': 'business.project.kpi',
            'view_mode': 'kanban,list,form,pivot,graph',
            'domain': domain,
            'context': {
                'default_employee_ids': [(4, self.user_id.id)] if self.user_id else [],
                'default_hr_employee_ids': [(4, self.id)],
                'search_default_group_stage_id': 1,
            },
            'target': 'current',
        }

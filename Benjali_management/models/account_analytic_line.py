from odoo import models, fields, api


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    business_project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        ondelete='cascade',
        index=True
    )
    kpi_id = fields.Many2one(
        'business.project.kpi',
        string='KPI',
        ondelete='cascade',
        index=True
    )

    @api.model
    def _find_or_create_project_analytic_account(self, bp=None):
        """Returns an active analytic account under the 'Project' plan."""
        Plan = self.env['account.analytic.plan']
        # 1. Identify the 'Project' analytic plan
        plan = (
            self.env.ref('hr_timesheet.analytic_plan_projects', raise_if_not_found=False)
            or self.env.ref('analytic.analytic_plan_projects', raise_if_not_found=False)
            or Plan.search([('name', 'ilike', 'project')], limit=1)
            or (hasattr(self.env.company, 'project_plan_id') and self.env.company.project_plan_id)
            or Plan.search([], limit=1)
        )
        if not plan:
            try:
                plan = Plan.create({'name': 'Projects'})
            except Exception:
                plan = Plan.search([], limit=1)

        Account = self.env['account.analytic.account']

        # 2. If business project has an allocated project.project with account_id, prioritize it
        if bp and bp.project_id and hasattr(bp.project_id, 'account_id') and bp.project_id.account_id:
            return bp.project_id.account_id

        # 3. Check if an account already exists for this business project and plan
        if bp and bp.name and plan:
            acc = Account.search([
                ('plan_id', '=', plan.id),
                ('name', '=', bp.name),
                '|', ('company_id', '=', bp.company_id.id if bp.company_id else self.env.company.id),
                     ('company_id', '=', False),
            ], limit=1)
            if acc:
                return acc

        # 4. Check for any active account in this plan for the current company
        if plan:
            acc = Account.search([
                ('plan_id', '=', plan.id),
                ('active', '=', True),
                '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False),
            ], limit=1)
            if acc:
                return acc

            # 5. Otherwise create a dedicated analytic account in the Project plan
            account_name = bp.name if bp and bp.name else 'KPI Timesheets'
            try:
                return Account.create({
                    'name': account_name,
                    'plan_id': plan.id,
                    'company_id': self.env.company.id,
                    'active': True,
                })
            except Exception:
                return Account.search([('active', '=', True)], limit=1)
        return False

    def _resolve_account_and_project(self, vals, record=None):
        """Resolves both account_id and standard project_id for the analytic line."""
        bp_id = vals.get('business_project_id') or (record.business_project_id.id if record and record.business_project_id else None)
        kpi_id = vals.get('kpi_id') or (record.kpi_id.id if record and record.kpi_id else None)

        bp = None
        if bp_id:
            bp = self.env['business.project'].browse(bp_id)
        elif kpi_id:
            kpi = self.env['business.project.kpi'].browse(kpi_id)
            bp = kpi.project_id

        # Populate business_project_id if missing
        if bp and not vals.get('business_project_id'):
            vals['business_project_id'] = bp.id

        # Populate standard project_id if business.project has an allocated project
        if bp and bp.project_id and not vals.get('project_id'):
            vals['project_id'] = bp.project_id.id

        # Populate account_id if missing
        if not vals.get('account_id'):
            if record and record.account_id:
                vals['account_id'] = record.account_id.id
            else:
                acc = self._find_or_create_project_analytic_account(bp)
                if acc:
                    vals['account_id'] = acc.id

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        bp_id = res.get('business_project_id') or self.env.context.get('default_business_project_id')
        kpi_id = res.get('kpi_id') or self.env.context.get('default_kpi_id')
        bp = self.env['business.project'].browse(bp_id) if bp_id else None
        if not bp and kpi_id:
            kpi = self.env['business.project.kpi'].browse(kpi_id)
            bp = kpi.project_id

        if not res.get('account_id'):
            acc = self._find_or_create_project_analytic_account(bp)
            if acc:
                res['account_id'] = acc.id

        if bp and bp.project_id and not res.get('project_id'):
            res['project_id'] = bp.project_id.id

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = '/'
            self._resolve_account_and_project(vals)
        return super().create(vals_list)

    def write(self, vals):
        if 'account_id' in vals and not vals['account_id']:
            for line in self:
                self._resolve_account_and_project(vals, record=line)
                break
        return super().write(vals)
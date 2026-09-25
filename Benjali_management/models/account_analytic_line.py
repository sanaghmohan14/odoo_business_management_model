from odoo import models, fields


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    business_project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        ondelete='cascade',
        index=True
    )
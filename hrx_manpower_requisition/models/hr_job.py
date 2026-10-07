from odoo import fields, models


class HrJob(models.Model):
    _inherit = 'hr.job'

    hrx_requisition_ids = fields.One2many(
        'manpower.requisition', 'job_id',
        string='Manpower Requisitions', readonly=True,
        groups='hrx_manpower_requisition.group_mpr_hr_exec,'
               'hrx_manpower_requisition.group_mpr_management',
    )
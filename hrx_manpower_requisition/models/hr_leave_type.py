from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    hrx_is_lop = fields.Boolean(
        'Loss of Pay (HRX)',
        help="Approved leave of this type is counted as Loss of Pay in the monthly attendance.")
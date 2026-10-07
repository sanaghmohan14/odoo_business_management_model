from odoo import fields, models


class ManpowerRequisitionRejectWizard(models.TransientModel):
    _name = 'manpower.requisition.reject.wizard'
    _description = 'Reject Manpower Requisition'

    requisition_id = fields.Many2one('manpower.requisition', required=True, ondelete='cascade')
    reason = fields.Text('Reason for Rejection', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.requisition_id._do_reject(self.reason)
        return {'type': 'ir.actions.act_window_close'}

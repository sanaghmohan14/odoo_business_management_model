from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrxEmpDoc(models.Model):
    _name = 'hrx.emp.doc'
    _description = 'Employee Document'
    _order = 'employee_id, type_id, id'

    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade', index=True)
    type_id = fields.Many2one('hrx.emp.doc.type', string='Document', required=True)
    category = fields.Selection(related='type_id.category', store=True, index=True)
    is_required = fields.Boolean(related='type_id.required', string='Required')
    file = fields.Binary('File', attachment=True)
    file_name = fields.Char('File Name')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('received', 'Received'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ], default='pending', required=True)
    remarks = fields.Char()
    verified_by = fields.Many2one('res.users', readonly=True)
    verified_date = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('file') and not vals.get('state'):
                vals['state'] = 'received'
        return super().create(vals_list)

    def write(self, vals):
        # A new or replaced file always needs (re)verification
        if 'file' in vals and 'state' not in vals:
            vals = dict(vals, state='received' if vals['file'] else 'pending',
                        verified_by=False, verified_date=False)
        return super().write(vals)

    def action_verify(self):
        for rec in self:
            if not rec.file:
                raise UserError(_("Upload a file for '%s' before verifying.", rec.type_id.name))
        self.write({
            'state': 'verified',
            'verified_by': self.env.user.id,
            'verified_date': fields.Datetime.now(),
        })

    def action_reject(self):
        for rec in self:
            if not rec.remarks:
                raise UserError(_("Enter remarks in '%s' explaining the rejection.",
                                  rec.type_id.name))
        self.write({'state': 'rejected', 'verified_by': self.env.user.id,
                    'verified_date': fields.Datetime.now()})
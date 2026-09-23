from odoo import models, fields
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True
    )

    business_project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        readonly=True
    )

    def action_create_business_project(self):
        self.ensure_one()

        # Check whether a Business Project already exists
        if self.business_project_id:
            raise UserError(
                'A Business Project already exists for this lead.'
            )


        # Check department
        if not self.department_id:
            raise UserError(
                'Please select a department before creating a Business Project.'
            )

        # A Business Project requires a client.
        if not self.partner_id:
            raise UserError(
                'Please select a customer before creating a Business Project.'
            )

        # Create Business Project
        business_project = self.env['business.project'].create({
            'name': self.name,
            'partner_id': self.partner_id.id,
            'opportunity_id': self.id,
            'sales_person_id': self.user_id.id,
            'department_id': self.department_id.id,

        })

        # Link the Business Project to the CRM Lead
        self.business_project_id = business_project.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Business Project',
            'res_model': 'business.project',
            'view_mode': 'form',
            'res_id': business_project.id,
            'target': 'current',
        }

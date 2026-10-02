from odoo import models, fields , api
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _check_company_auto = True

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

    project_task_id = fields.Many2one(
        'project.task',
        string='Project Task',
        readonly=True
    )

    project_assign_id = fields.Many2one(
        'project.project',
        'Assign Project',
        readonly=True,
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
        if not self. partner_id:
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

        # Create the related standard Odoo project. No project tasks or
        # subtasks are created here.
        project = self.env['project.project'].create({
            'name': self.name,
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id or self.env.user.id,
            'company_id': self.company_id.id or self.env.company.id,
            'department_id': self.department_id.id,
            'description': self.description,
            'allow_billable': True,
            'business_project_id': business_project.id,
        })

        # Keep both CRM links and the business project's project link in sync.
        business_project.project_id = project.id


        # Link the Business Project to the CRM Lead
        self.write({
            'business_project_id': business_project.id,
            'project_assign_id': project.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Business Project',
            'res_model': 'business.project',
            'view_mode': 'kanban,form',
            'res_id': business_project.id,
            'target': 'current',
        }










    def create_sale_quotation(self):

        project = self.project_assign_id
        if project:
            # Sale Order's Project field only allows billable projects.
            project.allow_billable = True

        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'project_id': project.id if project else False,

        })
        return{
            'type': 'ir.actions.act_window',
            'name': 'Sale quotation',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',

        }


    @api.onchange('tag_ids')
    def _onchange_tag_id(self):
        for rec in self:
            if rec.tag_ids:
                department = self.env['crm.tag'].search(
                [('id', 'in', rec.tag_ids.mapped('department_ids').ids)],
                limit=1 )
                if department:
                    rec.department_id = department.id




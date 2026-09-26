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

    project_task_id = fields.Many2one(
        'project.task',
        string='Project Task',
        readonly=True
    )

    project_assign_id = fields.Many2one(
        'project.project',
        'Assign Project',
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

        # Link the Business Project to the CRM Lead
        self.business_project_id = business_project.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Business Project',
            'res_model': 'business.project',
            'view_mode': 'kanban,form',
            'res_id': business_project.id,
            'target': 'current',
        }





    def action_open_project_task(self):
        self.ensure_one()

        # Check project
        if not self.project_assign_id:
            raise UserError(
                'Please select a project before opening project tasks.'
            )

        # Find first stage
        first_stage = self.env['project.task.type'].search(
            [
                ('name', '=', 'Client follow up')
            ],
            order='sequence, id',
            limit=1
        )

        if not first_stage:
            raise UserError(
                'Client follow up stage was not found.'
            )

        # Create task if it does not already exist
        if not self.project_task_id:

            task = self.env['project.task'].create({
                'name': self.name,
                'project_id': self.project_assign_id.id,
                'partner_id': self.partner_id.id,
                'stage_id': first_stage.id,
                'description': self.description,
            })

            self.project_task_id = task.id

        # Open project tasks in Kanban view
        return {
            'type': 'ir.actions.act_window',
            'name': self.project_assign_id.name + ' - Tasks',
            'res_model': 'project.task',
            'view_mode': 'kanban,list,form',
            'domain': [
                ('project_id', '=', self.project_assign_id.id)
            ],
            'context': {
                'default_project_id': self.project_assign_id.id,
            },
            'target': 'current',
        }




    def create_sale_quotation(self):

        sale_order=self.env['sale.order'].create({
            'partner_id':self.partner_id.id,
             'id':self.id,

        })
        return{
            'type': 'ir.actions.act_window',
            'name': 'Sale quotation',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',

        }
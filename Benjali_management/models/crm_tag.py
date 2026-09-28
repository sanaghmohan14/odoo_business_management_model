from odoo import api, fields, models, tools

class crm_tag(models.Model):
    _inherit = "crm.tag"

    department_ids = fields.Many2many('hr.department',string="Department")
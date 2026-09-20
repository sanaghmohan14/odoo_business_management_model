from odoo import api, fields, models, tools
from odoo.exceptions import ValidationError

class CrmLead(models.Model):
    _inherit = 'crm.lead'


    department_id = fields.Many2one('hr.department',string="Department")
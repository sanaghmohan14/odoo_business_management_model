from odoo import api,fields,models
from odoo.exceptions import ValidationError

class BusinessReportingWizard(models.TransientModel):
    _name = 'business.reporting.wizard'


    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    # partner_id = fields.Many2one('res.partner')
    # department_id = fields.Many2one('hr.department')
    # project_manager_id = fields.Many2one('res.users')


    def action_print_report(self):
        print("Pdf Report")

    def action_print_xlsx(self):
        print("xlsx Report")
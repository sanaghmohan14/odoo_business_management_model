from odoo import fields, models

HR_GROUP = 'hr_recruitment.group_hr_recruitment_user'


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    hrx_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', string='Currency')
    hrx_current_salary = fields.Monetary(
        'Current Salary', currency_field='hrx_currency_id', groups=HR_GROUP)
    hrx_total_experience = fields.Float(
        'Total Experience (years)', groups=HR_GROUP)
    hrx_notice_period = fields.Integer(
        'Notice Period (days)', groups=HR_GROUP)
    hrx_verification_state = fields.Selection([
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('mismatch', 'Mismatch Found'),
    ], string='Qualification/Experience Check', default='pending', groups=HR_GROUP)
    hrx_verification_note = fields.Text('Verification Notes', groups=HR_GROUP)
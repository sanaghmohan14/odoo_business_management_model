from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BusinessProjectDataCollection(models.Model):
    _name = 'business.project.data.collection'
    _description = 'Business Project Data Collection'
    _order = 'collection_date, id'

    project_id = fields.Many2one(
        'business.project',
        string='Business Project',
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        string='Data / Study Item',
        required=True
    )

    data_type = fields.Selection([
        ('interview', 'Client Interview'),
        ('document', 'Document'),
        ('process', 'Existing Process'),
        ('system', 'Existing System'),
        ('sales', 'Sales Data'),
        ('financial', 'Financial Data'),
        ('other', 'Other'),
    ], string='Type', required=True, default='other')

    description = fields.Text(
        string='Description'
    )

    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsible Person',
        required=True
    )

    collection_date = fields.Date(
        string='Collection Date'
    )

    source = fields.Char(
        string='Source'
    )

    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('collected', 'Collected'),
        ('verified', 'Verified'),
    ], string='Status', default='planned', required=True)

    notes = fields.Text(
        string='Notes'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.constrains('collection_date')
    def _check_collection_date(self):
        for record in self:
            if record.collection_date and record.collection_date > fields.Date.today():
                raise ValidationError(
                    'Collection Date cannot be in the future.'
                )
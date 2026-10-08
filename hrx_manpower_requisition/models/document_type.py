from odoo import fields, models


class HrxEmpDocType(models.Model):
    _name = 'hrx.emp.doc.type'
    _description = 'Employee Document Type'
    _order = 'category, sequence, id'

    name = fields.Char(required=True, translate=True)
    category = fields.Selection([
        ('joining', 'Joining'),
        ('exit', 'Exit'),
    ], default='joining', required=True)
    required = fields.Boolean(default=False)
    auto_add = fields.Boolean(
        'Add Automatically', default=True,
        help="Joining documents: added to every new employee's checklist. "
             "Exit documents are added with the 'Add Exit Documents' button instead.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
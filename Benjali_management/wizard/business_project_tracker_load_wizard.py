# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BusinessProjectTrackerLoadWizard(models.TransientModel):
    _name = 'business.project.tracker.load.wizard'
    _description = 'Load Scope Tracker from Template Wizard'

    project_id = fields.Many2one(
        'business.project',
        string='Project',
        required=True
    )
    template_id = fields.Many2one(
        'business.project.tracker.template',
        string='Scope Template',
        required=True,
        default=lambda self: self._default_template_id()
    )
    category_filter = fields.Selection([
        ('both', 'Both (Documentation & Implementation)'),
        ('documentation', 'Documentation Deliverables Only'),
        ('implementation', 'Implementation Activities Only'),
    ], string='Category Filter', default='both', required=True)

    scope_filter_mode = fields.Selection([
        ('all', 'All 30 Scopes (Scope 0 to 29)'),
        ('range', 'Scope Range (From - To)'),
        ('specific', 'Specific Scope Numbers'),
    ], string='Scope Filter Mode', default='all', required=True)

    scope_from = fields.Integer(
        string='Scope From',
        default=0
    )
    scope_to = fields.Integer(
        string='Scope To',
        default=29
    )
    scope_specific = fields.Char(
        string='Specific Scopes',
        placeholder='e.g. 0, 1, 2, 7, 15, 29'
    )

    default_accountable_id = fields.Many2one(
        'res.users',
        string='Default Accountable (TL / PM)'
    )
    default_responsible_id = fields.Many2one(
        'res.users',
        string='Default Responsible (Consultant / Doer)'
    )
    default_start_date = fields.Date(
        string='Default Start Date',
        default=fields.Date.today
    )
    default_end_date = fields.Date(
        string='Default Target Date'
    )
    skip_existing = fields.Boolean(
        string='Skip Already Added Deliverables',
        default=True,
        help='Do not duplicate deliverables that are already added to this project with the same Item ID.'
    )

    @api.model
    def _default_template_id(self):
        tmpl = self.env['business.project.tracker.template'].search([('active', '=', True)], limit=1)
        if not tmpl:
            tmpl = self.env['business.project.tracker.template'].create({
                'name': 'SME Advanced Edition (India & GCC)',
                'code': 'SME-ADV',
            })
            tmpl.action_load_default_master_data()
        return tmpl.id

    def action_load_trackers(self):
        self.ensure_one()
        template = self.template_id
        if not template.line_ids:
            template.action_load_default_master_data()

        lines = template.line_ids

        # 1. Filter by category
        if self.category_filter == 'documentation':
            lines = lines.filtered(lambda l: l.category == 'documentation')
        elif self.category_filter == 'implementation':
            lines = lines.filtered(lambda l: l.category == 'implementation')

        # 2. Filter by scope
        if self.scope_filter_mode == 'range':
            lines = lines.filtered(lambda l: self.scope_from <= l.scope_no <= self.scope_to)
        elif self.scope_filter_mode == 'specific' and self.scope_specific:
            scopes = []
            for s in self.scope_specific.split(','):
                s = s.strip()
                if s.isdigit():
                    scopes.append(int(s))
            if scopes:
                lines = lines.filtered(lambda l: l.scope_no in scopes)

        if not lines:
            raise UserError(_("No template deliverables matched your selected scope/category filters."))

        # 3. Skip existing
        existing_item_ids = set()
        if self.skip_existing:
            existing_item_ids = set(self.project_id.tracker_ids.mapped('item_id'))

        lines_to_add = [l for l in lines if l.item_id not in existing_item_ids] if existing_item_ids else lines

        if not lines_to_add:
            raise UserError(_("All %d matching deliverables are already loaded in this project.") % len(lines))

        vals_list = []
        for line in lines_to_add:
            vals_list.append({
                'project_id': self.project_id.id,
                'template_line_id': line.id,
                'item_id': line.item_id,
                'scope_no': line.scope_no,
                'scope_name': line.scope_name,
                'scope_pillar': line.scope_pillar,
                'category': line.category,
                'item_no': line.item_no,
                'name': line.name,
                'item_type': line.item_type,
                'evidence_required': line.evidence_proof,
                'final_approval_authority': line.approval_authority,
                'accountable_id': self.default_accountable_id.id if self.default_accountable_id else False,
                'responsible_id': self.default_responsible_id.id if self.default_responsible_id else False,
                'start_date': self.default_start_date or False,
                'end_date': self.default_end_date or False,
                'state': 'not_started',
                'progress': 0.0,
            })

        self.env['business.project.tracker'].create(vals_list)

        self.project_id.message_post(
            body=_("Loaded %d Scope Tracker deliverables from template '%s'.") % (
                len(vals_list), template.name
            ),
            subject=_("Scope Trackers Loaded")
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Scope Trackers Loaded'),
                'message': _('Successfully loaded %d deliverables into project %s.') % (
                    len(vals_list), self.project_id.name
                ),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

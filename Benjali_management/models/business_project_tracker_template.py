# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BusinessProjectTrackerTemplate(models.Model):
    _name = 'business.project.tracker.template'
    _description = 'Scope Tracker Master Template'
    _order = 'name'

    name = fields.Char(
        string='Template Name',
        required=True,
        default='SME Advanced Edition (India & GCC)'
    )
    code = fields.Char(
        string='Template Code',
        default='SME-ADV',
        index=True
    )
    description = fields.Text(
        string='Description',
        default='SCOPE-WISE TASK LIST - SME ADVANCED EDITION (INDIA & GCC) with 30 Scopes (718 Documents & 664 Activities).'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    line_ids = fields.One2many(
        'business.project.tracker.template.line',
        'template_id',
        string='Template Lines',
        copy=True
    )

    total_items = fields.Integer(
        string='Total Items',
        compute='_compute_template_stats',
        store=True
    )
    total_scopes = fields.Integer(
        string='Total Scopes',
        compute='_compute_template_stats',
        store=True
    )
    total_documents = fields.Integer(
        string='Documents',
        compute='_compute_template_stats',
        store=True
    )
    total_activities = fields.Integer(
        string='Activities',
        compute='_compute_template_stats',
        store=True
    )

    @api.depends('line_ids', 'line_ids.category', 'line_ids.scope_no')
    def _compute_template_stats(self):
        for rec in self:
            rec.total_items = len(rec.line_ids)
            rec.total_scopes = len(set(rec.line_ids.mapped('scope_no')))
            rec.total_documents = len(rec.line_ids.filtered(lambda l: l.category == 'documentation'))
            rec.total_activities = len(rec.line_ids.filtered(lambda l: l.category == 'implementation'))

    def action_load_default_master_data(self):
        """Load or update default 1,382 items from scope_tracker_master_data into this template."""
        self.ensure_one()
        from ..data.scope_tracker_master_data import get_master_tracker_records
        master_data = get_master_tracker_records()
        LineObj = self.env['business.project.tracker.template.line']
        existing_lines = {l.item_id: l for l in self.line_ids if l.item_id}

        to_create = []
        updated_count = 0

        for item in master_data:
            item_id = item.get('item_id')
            vals = {
                'template_id': self.id,
                'item_id': item_id,
                'scope_no': item.get('scope_no', 0),
                'scope_name': item.get('scope_name', ''),
                'scope_pillar': item.get('scope_pillar', ''),
                'category': item.get('category', 'documentation'),
                'item_no': item.get('item_no', 1),
                'name': item.get('name', ''),
                'item_type': item.get('item_type', ''),
                'evidence_proof': item.get('evidence_proof', ''),
                'approval_authority': item.get('approval_authority', 'TL'),
            }
            if item_id in existing_lines:
                existing_lines[item_id].write(vals)
                updated_count += 1
            else:
                to_create.append(vals)

        if to_create:
            LineObj.create(to_create)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Master Data Loaded'),
                'message': _('Successfully loaded %d records (Created: %d, Updated: %d).') % (
                    len(master_data), len(to_create), updated_count
                ),
                'sticky': False,
                'type': 'success',
            }
        }

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            'name': _('Import Template from Excel'),
            'type': 'ir.actions.act_window',
            'res_model': 'business.project.tracker.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_template_id': self.id},
        }


class BusinessProjectTrackerTemplateLine(models.Model):
    _name = 'business.project.tracker.template.line'
    _description = 'Scope Tracker Master Template Line'
    _order = 'scope_no, category desc, item_no, sequence, id'

    template_id = fields.Many2one(
        'business.project.tracker.template',
        string='Template',
        required=True,
        default=lambda self: self.env['business.project.tracker.template'].search([], limit=1).id,
        ondelete='cascade',
        index=True
    )
    item_id = fields.Char(
        string='Item ID',
        required=True,
        index=True
    )
    scope_no = fields.Integer(
        string='Scope No',
        required=True,
        default=0,
        index=True
    )
    scope_name = fields.Char(
        string='Scope',
        required=True,
        index=True
    )
    scope = fields.Char(
        string='Scope',
        compute='_compute_scope',
        inverse='_inverse_scope',
        search='_search_scope',
        store=True,
        index=True
    )
    scope_pillar = fields.Char(
        string='Pillar',
        index=True
    )
    category = fields.Selection([
        ('documentation', 'Documentation'),
        ('implementation', 'Implementation'),
    ], string='Category', required=True, index=True, default='documentation')
    item_no = fields.Integer(
        string='Item No',
        default=1
    )
    name = fields.Char(
        string='Item Name',
        required=True
    )
    item_name = fields.Char(
        string='Item Name',
        compute='_compute_item_name',
        inverse='_inverse_item_name',
        search='_search_item_name',
        store=True
    )
    item_type = fields.Char(
        string='Item Type'
    )
    evidence_proof = fields.Text(
        string='Evidence / Proof'
    )
    evidence_required = fields.Text(
        string='Evidence / Proof Required',
        compute='_compute_evidence_required',
        inverse='_inverse_evidence_required',
        store=True
    )
    approval_authority = fields.Selection([
        ('TL', 'Team Lead (TL)'),
        ('PM', 'Project Manager (PM)'),
        ('VP', 'Vice President (VP)'),
        ('CEO', 'Chief Executive Officer (CEO)'),
    ], string='Approval Authority', required=True, default='TL', index=True)
    final_approval_authority = fields.Selection([
        ('TL', 'Team Lead (TL)'),
        ('PM', 'Project Manager (PM)'),
        ('VP', 'Vice President (VP)'),
        ('CEO', 'Chief Executive Officer (CEO)'),
    ], string='Final Approval Authority', compute='_compute_final_approval_authority', inverse='_inverse_final_approval_authority', store=True)
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    @api.depends('scope_name')
    def _compute_scope(self):
        for rec in self:
            rec.scope = rec.scope_name

    def _inverse_scope(self):
        for rec in self:
            if rec.scope and not rec.scope_name:
                rec.scope_name = rec.scope

    def _search_scope(self, operator, value):
        return [('scope_name', operator, value)]

    @api.depends('name')
    def _compute_item_name(self):
        for rec in self:
            rec.item_name = rec.name

    def _inverse_item_name(self):
        for rec in self:
            if rec.item_name and not rec.name:
                rec.name = rec.item_name

    def _search_item_name(self, operator, value):
        return [('name', operator, value)]

    @api.depends('evidence_proof')
    def _compute_evidence_required(self):
        for rec in self:
            rec.evidence_required = rec.evidence_proof

    def _inverse_evidence_required(self):
        for rec in self:
            if rec.evidence_required and not rec.evidence_proof:
                rec.evidence_proof = rec.evidence_required

    @api.depends('approval_authority')
    def _compute_final_approval_authority(self):
        for rec in self:
            rec.final_approval_authority = rec.approval_authority

    def _inverse_final_approval_authority(self):
        for rec in self:
            if rec.final_approval_authority and not rec.approval_authority:
                rec.approval_authority = rec.final_approval_authority

    @api.model_create_multi
    def create(self, vals_list):
        default_tpl = self.env.context.get('default_template_id') or self.env['business.project.tracker.template'].search([], limit=1).id
        for vals in vals_list:
            if not vals.get('template_id') and default_tpl:
                vals['template_id'] = default_tpl
            if 'item_name' in vals and not vals.get('name'):
                vals['name'] = vals['item_name']
            elif 'name' in vals and not vals.get('item_name'):
                vals['item_name'] = vals['name']
            if 'scope' in vals and not vals.get('scope_name'):
                vals['scope_name'] = vals['scope']
            elif 'scope_name' in vals and not vals.get('scope'):
                vals['scope'] = vals['scope_name']
            if 'evidence_required' in vals and not vals.get('evidence_proof'):
                vals['evidence_proof'] = vals['evidence_required']
            elif 'evidence_proof' in vals and not vals.get('evidence_required'):
                vals['evidence_required'] = vals['evidence_proof']
            if 'final_approval_authority' in vals and not vals.get('approval_authority'):
                vals['approval_authority'] = vals['final_approval_authority']
            elif 'approval_authority' in vals and not vals.get('final_approval_authority'):
                vals['final_approval_authority'] = vals['approval_authority']
        return super().create(vals_list)

    def write(self, vals):
        if 'item_name' in vals and 'name' not in vals:
            vals['name'] = vals['item_name']
        elif 'name' in vals and 'item_name' not in vals:
            vals['item_name'] = vals['name']
        if 'scope' in vals and 'scope_name' not in vals:
            vals['scope_name'] = vals['scope']
        elif 'scope_name' in vals and 'scope' not in vals:
            vals['scope'] = vals['scope_name']
        if 'evidence_required' in vals and 'evidence_proof' not in vals:
            vals['evidence_proof'] = vals['evidence_required']
        elif 'evidence_proof' in vals and 'evidence_required' not in vals:
            vals['evidence_required'] = vals['evidence_proof']
        if 'final_approval_authority' in vals and 'approval_authority' not in vals:
            vals['approval_authority'] = vals['final_approval_authority']
        elif 'approval_authority' in vals and 'final_approval_authority' not in vals:
            vals['final_approval_authority'] = vals['approval_authority']
        return super().write(vals)

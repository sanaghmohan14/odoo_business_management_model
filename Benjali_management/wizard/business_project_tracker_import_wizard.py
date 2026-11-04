# -*- coding: utf-8 -*-
import base64
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None


class BusinessProjectTrackerImportWizard(models.TransientModel):
    _name = 'business.project.tracker.import.wizard'
    _description = 'Import Scope Tracker Template Wizard'

    template_id = fields.Many2one(
        'business.project.tracker.template',
        string='Target Template',
        required=True
    )
    import_source = fields.Selection([
        ('default_master', 'Load Pre-packaged Master Data (1,382 Records - SME Advanced)'),
        ('excel_file', 'Upload Excel Spreadsheet (.xlsx)'),
    ], string='Source', default='default_master', required=True)

    excel_file = fields.Binary(
        string='Excel File (.xlsx)'
    )
    excel_filename = fields.Char(
        string='File Name'
    )
    sheet_name = fields.Char(
        string='Sheet Name (Optional)',
        help='Name of the sheet to import. If left blank, the first sheet will be used.'
    )
    clear_existing = fields.Boolean(
        string='Clear existing template lines first',
        default=False
    )

    def action_import(self):
        self.ensure_one()
        template = self.template_id

        if self.clear_existing:
            template.line_ids.unlink()

        if self.import_source == 'default_master':
            return template.action_load_default_master_data()

        if not self.excel_file:
            raise UserError(_("Please upload an Excel (.xlsx) file to import."))

        if not openpyxl:
            raise UserError(_("Python library 'openpyxl' is required to read Excel files."))

        try:
            file_data = base64.b64decode(self.excel_file)
            wb = openpyxl.load_workbook(io.BytesIO(file_data), data_only=True)
        except Exception as e:
            raise UserError(_("Failed to read the Excel file: %s") % str(e))

        if self.sheet_name and self.sheet_name in wb.sheetnames:
            sheet = wb[self.sheet_name]
        else:
            sheet = wb.active

        # Find header row
        header_row_idx = None
        col_map = {}
        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            row_str = [str(c).strip().lower() if c is not None else '' for c in row]
            if any('item_id' in c or 'item id' in c for c in row_str):
                header_row_idx = row_idx
                for col_idx, cell_val in enumerate(row_str):
                    if cell_val:
                        col_map[cell_val] = col_idx
                break

        if header_row_idx is None:
            raise UserError(_(
                "Could not find the header row containing 'Item_ID'. Please ensure the sheet has columns: Item_ID, Scope_No, Scope_Name, Scope_Pillar, Category, Item_No, Item_Name, Item_Type, Evidence_Proof, Approval_Authority."
            ))

        def get_val(row, *aliases):
            for a in aliases:
                idx = col_map.get(a.lower())
                if idx is not None and idx < len(row):
                    val = row[idx]
                    if val is not None:
                        return str(val).strip()
            return ''

        existing_lines = {l.item_id: l for l in template.line_ids if l.item_id}
        to_create = []
        updated_count = 0

        for row in sheet.iter_rows(min_row=header_row_idx + 1, values_only=True):
            if not any(row):
                continue
            item_id = get_val(row, 'item_id', 'item id', 'id')
            if not item_id:
                continue

            scope_no_str = get_val(row, 'scope_no', 'scope no', 'scope_number')
            try:
                scope_no = int(float(scope_no_str)) if scope_no_str else 0
            except ValueError:
                scope_no = 0

            scope_name = get_val(row, 'scope_name', 'scope name', 'scope', 'scope (functional area)')
            scope_pillar = get_val(row, 'scope_pillar', 'pillar')
            category_raw = get_val(row, 'category', 'type').lower()
            category = 'implementation' if 'impl' in category_raw else 'documentation'

            item_no_str = get_val(row, 'item_no', 'item no', 'no')
            try:
                item_no = int(float(item_no_str)) if item_no_str else 1
            except ValueError:
                item_no = 1

            name = get_val(row, 'item_name', 'item name', 'name', 'deliverable', 'description')
            item_type = get_val(row, 'item_type', 'item type', 'type')
            evidence_proof = get_val(row, 'evidence_proof', 'evidence / proof', 'evidence', 'proof')
            authority_raw = get_val(row, 'approval_authority', 'approval authority', 'authority', 'final approval authority').upper()

            authority = 'TL'
            if 'CEO' in authority_raw:
                authority = 'CEO'
            elif 'VP' in authority_raw:
                authority = 'VP'
            elif 'PM' in authority_raw:
                authority = 'PM'
            elif 'TL' in authority_raw:
                authority = 'TL'

            vals = {
                'template_id': template.id,
                'item_id': item_id,
                'scope_no': scope_no,
                'scope_name': scope_name or ('Scope %d' % scope_no),
                'scope_pillar': scope_pillar,
                'category': category,
                'item_no': item_no,
                'name': name or item_id,
                'item_type': item_type,
                'evidence_proof': evidence_proof,
                'approval_authority': authority,
            }

            if item_id in existing_lines:
                existing_lines[item_id].write(vals)
                updated_count += 1
            else:
                to_create.append(vals)

        if to_create:
            self.env['business.project.tracker.template.line'].create(to_create)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Excel Import Complete'),
                'message': _('Successfully imported %d items (Created: %d, Updated: %d).') % (
                    len(to_create) + updated_count, len(to_create), updated_count
                ),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

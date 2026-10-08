from . import models
from . import wizard

from odoo import fields


def post_init_hook(env):
    """Give every existing employee a Joining event."""
    Event = env['hrx.employee.event'].with_context(hrx_wf=True)
    for emp in env['hr.employee'].with_context(active_test=False).search([]):
        Event.create({
            'employee_id': emp.id,
            'event_type': 'joining',
            'date': emp.hrx_joining_date or fields.Date.context_today(emp),
            'state': 'approved',
            'approval_date': fields.Datetime.now(),
            'reason': 'Existing employee at module installation.',
        })

from datetime import date, timedelta
from odoo import api, fields, models


class BenjaliManagementDashboard(models.AbstractModel):
    _name = 'benjali.management.dashboard'
    _description = 'Benjali Management Dashboard'

    @api.model
    def get_dashboard_data(self, *args, **kwargs):
        department_id = False
        if args:
            department_id = args[0]
        elif 'department_id' in kwargs:
            department_id = kwargs['department_id']
        elif self.ids:
            department_id = self.ids[0]

        try:
            department_id = int(department_id) if department_id else False
        except (TypeError, ValueError):
            department_id = False

        Project = self.env['business.project']
        Department = self.env['hr.department']
        Stage = self.env['business.project.stage']
        SOP = self.env['business.project.sop']
        Approval = self.env['business.project.approval']

        # Department vibrant accent color palette
        PALETTE = [
            '#3b82f6',  # Blue (Engineering)
            '#a855f7',  # Purple (Marketing)
            '#10b981',  # Emerald Green (Sales)
            '#f59e0b',  # Amber/Orange (Finance)
            '#ec4899',  # Pink (People)
            '#06b6d4',  # Cyan (Operations)
            '#6366f1',  # Indigo
            '#14b8a6',  # Teal
        ]

        # Fetch all departments
        all_departments = Department.search([], order='name')
        dep_color_map = {}
        for idx, dep in enumerate(all_departments):
            dep_color_map[dep.id] = PALETTE[idx % len(PALETTE)]

        # Fetch all projects
        all_projects = Project.search([])

        # Build department summary list for sidebar and widget
        departments_data = []
        for dep in all_departments:
            dep_projects = all_projects.filtered(lambda p: p.department_id.id == dep.id)
            count = len(dep_projects)
            spent_k = sum((p.kra_monthly_progress or 50) * 1.5 for p in dep_projects)
            total_k = count * 180
            if count > 0 and spent_k == 0:
                spent_k = count * 95
            if total_k == 0:
                total_k = 100
            pct = min(100, int((spent_k / total_k) * 100)) if total_k else 0

            departments_data.append({
                'id': dep.id,
                'name': dep.name,
                'count': count,
                'color': dep_color_map.get(dep.id, '#3b82f6'),
                'budget_spent': int(spent_k),
                'budget_total': int(total_k),
                'budget_str': f"${int(spent_k)}K / ${int(total_k)}K" if count > 0 else "$0K / $0K",
                'progress': pct,
            })

        # Filter projects according to department_id
        if department_id:
            filtered_projects = all_projects.filtered(lambda p: p.department_id.id == department_id)
            selected_dep = Department.browse(department_id)
            current_title = selected_dep.name if selected_dep.exists() else 'All departments'
        else:
            filtered_projects = all_projects
            current_title = 'All departments'

        today = fields.Date.today()

        # Build detailed project list with project-wise KRAs and KPIs
        projects_list = []
        for p in filtered_projects:
            # Stage-based progress calculation:
            # Progress is strictly determined by the project workflow stage (Completed stage = 100%)
            stage_name = (p.stage_id.name or '').strip().lower() if p.stage_id else ''
            if p.is_completed or stage_name == 'completed' or (p.stage_id and p.stage_id.phase == 'closure'):
                prog = 100
            elif p.is_cancelled or stage_name == 'cancelled':
                prog = 0
            elif stage_name == 'on hold':
                prog = 50
            elif p.stage_id:
                STAGE_PROGRESS_MAP = {
                    'new': 10,
                    'client onboarding': 25,
                    'project creation & initial client connection': 45,
                    'internal project understanding & team designation': 65,
                    'project setup & communication': 85,
                    'completed': 100,
                }
                if stage_name in STAGE_PROGRESS_MAP:
                    prog = STAGE_PROGRESS_MAP[stage_name]
                else:
                    all_stages = Stage.search([('active', '=', True)], order='sequence, id')
                    active_flow = [s for s in all_stages if (s.name or '').strip().lower() not in ('cancelled', 'on hold')]
                    if active_flow:
                        try:
                            s_idx = [s.id for s in active_flow].index(p.stage_id.id)
                            prog = int(round(((s_idx + 1) / len(active_flow)) * 100))
                        except ValueError:
                            prog = min(95, max(10, int(p.stage_id.sequence or 10)))
                    else:
                        prog = 50
            else:
                prog = 0

            # Determine status
            if p.is_completed or stage_name == 'completed' or prog >= 100:
                status = 'done'
                status_label = 'Done'
                prog = 100
            elif p.expected_end_date and p.expected_end_date < today:
                status = 'delayed'
                status_label = 'Delayed'
            elif p.is_on_hold or stage_name == 'on hold':
                status = 'at_risk'
                status_label = 'On Hold'
            elif p.priority in ('2', '3'):
                status = 'at_risk'
                status_label = 'At risk'
            else:
                status = 'on_track'
                status_label = 'On track'

            dep_color = dep_color_map.get(p.department_id.id, '#3b82f6') if p.department_id else '#94a3b8'
            owner = p.project_manager_id.name or p.responsible_user_id.name or 'Unassigned'

            # Date formatting
            end_date_str = ''
            days_str = ''
            if p.expected_end_date:
                end_date_str = p.expected_end_date.strftime('%b %d')
                delta_days = (p.expected_end_date - today).days
                if delta_days < 0:
                    days_str = f"{abs(delta_days)}d overdue"
                else:
                    days_str = f"{delta_days}d"

            # Project KRAs & KPIs breakdown
            kras_list = []
            for kra in p.kra_ids:
                kpis_list = []
                for kpi in kra.kpi_ids:
                    emp_names = [u.name for u in kpi.employee_ids]
                    assigned_str = ', '.join(emp_names) if emp_names else (kpi.employee_id.name if kpi.employee_id else 'Unassigned')
                    kpi_users_list = []
                    kpi_seen_u = set()
                    users_to_check = kpi.employee_ids or (kpi.employee_id if kpi.employee_id else self.env['res.users'])
                    for u in users_to_check:
                        if u.id not in kpi_seen_u:
                            kpi_seen_u.add(u.id)
                            kpi_users_list.append({
                                'id': u.id,
                                'name': u.name,
                                'email': u.email or '',
                                'initials': ''.join([part[0].upper() for part in u.name.split()[:2]]) if u.name else 'EM',
                            })
                    subtask_count = len(kpi.subtask_ids)
                    subtask_completed = len(kpi.subtask_ids.filtered(lambda s: s.state in ('completed', 'done')))
                    kpis_list.append({
                        'id': kpi.id,
                        'name': kpi.name or 'Task',
                        'code': kpi.code or 'Task',
                        'kra_id': kra.id,
                        'kra_name': kra.name or 'Scope',
                        'project_id': p.id,
                        'project_name': p.name,
                        'employee': assigned_str,
                        'employees': kpi_users_list,
                        'target': kpi.weekly_target or '-',
                        'progress': int(kpi.progress or 0),
                        'state': kpi.state or 'not_started',
                        'state_label': dict(kpi._fields['state'].selection).get(kpi.state, kpi.state) if 'state' in kpi._fields else kpi.state,
                        'stage_id': kpi.stage_id.id if kpi.stage_id else False,
                        'stage_name': kpi.stage_id.name if kpi.stage_id else '',
                        'hours_spent': round(kpi.total_hours_spent or 0.0, 1),
                        'priority': kpi.priority or '0',
                        'timesheet_count': len(kpi.timesheet_ids),
                        'subtask_count': subtask_count,
                        'subtask_completed_count': subtask_completed,
                        'is_repeating': bool(kpi.is_repeating or kpi.is_daily_repeating),
                    })

                lead_name = kra.responsible_user_id.name if kra.responsible_user_id else 'Unassigned'
                kra_emp_list = []
                seen_k_emp = set()
                for emp in kra.employee_ids:
                    if emp.id not in seen_k_emp:
                        seen_k_emp.add(emp.id)
                        kra_emp_list.append({
                            'id': emp.id,
                            'name': emp.name,
                            'email': emp.email or '',
                            'initials': ''.join([part[0].upper() for part in emp.name.split()[:2]]) if emp.name else 'EM',
                        })

                kras_list.append({
                    'id': kra.id,
                    'name': kra.name or 'Scope',
                    'code': kra.reference or 'Scope',
                    'project_id': p.id,
                    'project_name': p.name,
                    'lead': lead_name,
                    'manager_id': kra.responsible_user_id.id if kra.responsible_user_id else False,
                    'employees': kra_emp_list,
                    'employee_names_str': ', '.join([e['name'] for e in kra_emp_list]) if kra_emp_list else 'None',
                    'weekly_progress': int(kra.weekly_progress or kra.progress_percentage or 0),
                    'monthly_achievement': int(kra.monthly_achievement or 0),
                    'state': kra.state or 'new',
                    'state_label': dict(kra._fields['state'].selection).get(kra.state, kra.state) if 'state' in kra._fields else kra.state,
                    'stage_id': kra.stage_id.id if kra.stage_id else False,
                    'stage_name': kra.stage_id.name if kra.stage_id else '',
                    'priority': kra.priority or '0',
                    'start_date': kra.start_date.strftime('%b %d, %Y') if kra.start_date else '',
                    'end_date': kra.end_date.strftime('%b %d, %Y') if kra.end_date else '',
                    'kpis': kpis_list,
                    'kpi_count': len(kpis_list),
                    'completed_kpi_count': len([k for k in kpis_list if k['state'] == 'completed']),
                })

            # Project Manager & Project Responsible details
            pm_obj = p.project_manager_id
            pm_name = pm_obj.name if pm_obj else 'Unassigned'
            pm_email = pm_obj.email if pm_obj and pm_obj.email else ''
            pm_initials = ''.join([part[0].upper() for part in pm_name.split()[:2]]) if pm_obj else 'PM'

            pr_obj = p.responsible_user_id
            pr_name = pr_obj.name if pr_obj else 'Unassigned'
            pr_email = pr_obj.email if pr_obj and pr_obj.email else ''
            pr_initials = ''.join([part[0].upper() for part in pr_name.split()[:2]]) if pr_obj else 'PR'

            # Build comprehensive employee performance matrix for this project
            emp_perf_dict = {}

            if pm_obj:
                emp_perf_dict[pm_obj.id] = {
                    'id': pm_obj.id,
                    'name': pm_obj.name,
                    'email': pm_obj.email or '',
                    'initials': pm_initials,
                    'roles': ['Project Manager'],
                    'is_pm': True,
                    'is_responsible': False,
                    'kras': [],
                    'kpis': [],
                }

            if pr_obj:
                if pr_obj.id not in emp_perf_dict:
                    emp_perf_dict[pr_obj.id] = {
                        'id': pr_obj.id,
                        'name': pr_obj.name,
                        'email': pr_obj.email or '',
                        'initials': pr_initials,
                        'roles': ['Project Responsible'],
                        'is_pm': False,
                        'is_responsible': True,
                        'kras': [],
                        'kpis': [],
                    }
                else:
                    if 'Project Responsible' not in emp_perf_dict[pr_obj.id]['roles']:
                        emp_perf_dict[pr_obj.id]['roles'].append('Project Responsible')
                    emp_perf_dict[pr_obj.id]['is_responsible'] = True

            for kra_item in kras_list:
                kra_id = kra_item['id']
                kra_name = kra_item['name']
                kra_code = kra_item['code']
                kra_prog = kra_item['weekly_progress']
                kra_st = kra_item['state']
                kra_lead_id = kra_item['manager_id']

                # KRA Lead
                if kra_lead_id:
                    mgr_record = self.env['res.users'].browse(kra_lead_id)
                    if mgr_record.exists():
                        if kra_lead_id not in emp_perf_dict:
                            emp_perf_dict[kra_lead_id] = {
                                'id': kra_lead_id,
                                'name': mgr_record.name,
                                'email': mgr_record.email or '',
                                'initials': ''.join([part[0].upper() for part in mgr_record.name.split()[:2]]) if mgr_record.name else 'KM',
                                'roles': ['Scope Lead'],
                                'is_pm': False,
                                'is_responsible': False,
                                'kras': [],
                                'kpis': [],
                            }
                        elif 'Scope Lead' not in emp_perf_dict[kra_lead_id]['roles']:
                            emp_perf_dict[kra_lead_id]['roles'].append('Scope Lead')

                        if not any(k['id'] == kra_id for k in emp_perf_dict[kra_lead_id]['kras']):
                            emp_perf_dict[kra_lead_id]['kras'].append({
                                'id': kra_id,
                                'name': kra_name,
                                'code': kra_code,
                                'role': 'Lead / Manager',
                                'progress': kra_prog,
                                'state': kra_st,
                            })

                # KRA Assigned Employees
                for emp_info in kra_item['employees']:
                    eid = emp_info['id']
                    if eid not in emp_perf_dict:
                        emp_perf_dict[eid] = {
                            'id': eid,
                            'name': emp_info['name'],
                            'email': emp_info['email'],
                            'initials': emp_info['initials'],
                            'roles': ['Scope Member'],
                            'is_pm': False,
                            'is_responsible': False,
                            'kras': [],
                            'kpis': [],
                        }
                    elif 'Scope Member' not in emp_perf_dict[eid]['roles'] and 'Scope Lead' not in emp_perf_dict[eid]['roles']:
                        emp_perf_dict[eid]['roles'].append('Scope Member')

                    if not any(k['id'] == kra_id for k in emp_perf_dict[eid]['kras']):
                        emp_perf_dict[eid]['kras'].append({
                            'id': kra_id,
                            'name': kra_name,
                            'code': kra_code,
                            'role': 'Assigned Member',
                            'progress': kra_prog,
                            'state': kra_st,
                        })

                # KPI Assignees and progress
                for kpi_item in kra_item['kpis']:
                    kpi_info = {
                        'id': kpi_item['id'],
                        'name': kpi_item['name'],
                        'code': kpi_item['code'],
                        'kra_id': kra_id,
                        'kra_name': kra_name,
                        'progress': kpi_item['progress'],
                        'state': kpi_item['state'],
                        'state_label': kpi_item['state_label'],
                        'subtask_count': kpi_item['subtask_count'],
                        'subtask_completed_count': kpi_item['subtask_completed_count'],
                        'hours_spent': kpi_item['hours_spent'],
                        'priority': kpi_item.get('priority', '0'),
                        'target': kpi_item['target'],
                    }
                    for u_info in kpi_item['employees']:
                        uid = u_info['id']
                        if uid not in emp_perf_dict:
                            emp_perf_dict[uid] = {
                                'id': uid,
                                'name': u_info['name'],
                                'email': u_info['email'],
                                'initials': u_info['initials'],
                                'roles': ['KPI Assignee'],
                                'is_pm': False,
                                'is_responsible': False,
                                'kras': [],
                                'kpis': [],
                            }
                        elif 'KPI Assignee' not in emp_perf_dict[uid]['roles']:
                            emp_perf_dict[uid]['roles'].append('KPI Assignee')

                        if not any(k['id'] == kpi_item['id'] for k in emp_perf_dict[uid]['kpis']):
                            emp_perf_dict[uid]['kpis'].append(kpi_info)

            # Allocated Team Members (derived from Project Manager, Project Responsible, and Scopes & Tasks)
            team_members = []
            if p.project_manager_id:
                pm_u = p.project_manager_id
                pm_initials = ''.join([part[0].upper() for part in pm_u.name.split()[:2]]) if pm_u.name else 'PM'
                team_members.append({
                    'id': pm_u.id,
                    'name': pm_u.name,
                    'initials': pm_initials,
                    'role': 'project_manager',
                    'role_label': 'Project Manager',
                    'notes': '',
                })
            if p.responsible_user_id and p.responsible_user_id != p.project_manager_id:
                resp_u = p.responsible_user_id
                resp_initials = ''.join([part[0].upper() for part in resp_u.name.split()[:2]]) if resp_u.name else 'TL'
                team_members.append({
                    'id': resp_u.id,
                    'name': resp_u.name,
                    'initials': resp_initials,
                    'role': 'team_lead',
                    'role_label': 'Project Responsible / Team Lead',
                    'notes': '',
                })
            seen_uids = {tm['id'] for tm in team_members}
            for uid, emp_data in emp_perf_dict.items():
                if uid not in seen_uids:
                    team_members.append({
                        'id': uid,
                        'name': emp_data['name'],
                        'initials': emp_data['initials'],
                        'role': 'consultant',
                        'role_label': 'Consultant / Task Assignee',
                        'notes': '',
                    })
                    seen_uids.add(uid)

            # 1. Compute frontline employees (team members directly assigned to KRAs and KPIs)
            frontline_employees = []
            for emp in emp_perf_dict.values():
                if not emp.get('is_pm') and not emp.get('is_responsible'):
                    k_count = len(emp['kpis'])
                    comp_count = len([k for k in emp['kpis'] if k['state'] == 'completed'])
                    in_prog_count = len([k for k in emp['kpis'] if k['state'] == 'in_progress'])
                    avg_prog = int(sum(k['progress'] for k in emp['kpis']) / k_count) if k_count else 0
                    total_hours = round(sum(k['hours_spent'] for k in emp['kpis']), 1)

                    if k_count == 0:
                        perf_label = 'Assigned'
                        perf_badge = 'info'
                    elif avg_prog >= 80 or (k_count > 0 and comp_count == k_count):
                        perf_label = 'High Performer'
                        perf_badge = 'success'
                    elif avg_prog >= 50:
                        perf_label = 'On Track'
                        perf_badge = 'primary'
                    else:
                        perf_label = 'Needs Focus'
                        perf_badge = 'warning'

                    emp.update({
                        'kpi_count': k_count,
                        'completed_kpi_count': comp_count,
                        'in_progress_kpi_count': in_prog_count,
                        'avg_progress': avg_prog,
                        'total_hours': total_hours,
                        'performance_label': perf_label,
                        'performance_badge': perf_badge,
                        'kra_count': len(emp['kras']),
                        'is_leadership': False,
                        'hierarchy_level': 3,
                    })
                    frontline_employees.append(emp)

            # 2. Derive team-level aggregate employee performance:
            # Under Project Responsible are the employees!
            # Under Project Manager is the Project Responsible!
            emps_with_kpis = [e for e in frontline_employees if e['kpi_count'] > 0]
            if emps_with_kpis:
                emp_team_avg_prog = int(sum(e['avg_progress'] for e in emps_with_kpis) / len(emps_with_kpis))
                emp_team_kpis_completed = sum(e['completed_kpi_count'] for e in emps_with_kpis)
                emp_team_kpis_total = sum(e['kpi_count'] for e in emps_with_kpis)
                emp_team_total_hours = round(sum(e['total_hours'] for e in emps_with_kpis), 1)
            else:
                emp_team_avg_prog = int(prog)  # fallback to project progress
                emp_team_kpis_completed = sum(k['completed_kpi_count'] for k in kras_list)
                emp_team_kpis_total = sum(k['kpi_count'] for k in kras_list)
                emp_team_total_hours = 0.0

            # 3. Compute Project Responsible performance (Hierarchical Level 2: Supervised Employees)
            # Under Project Responsible are the Employees. Responsible performance is based on employees performance!
            resp_score = emp_team_avg_prog
            if resp_score >= 80 or (emp_team_kpis_total > 0 and emp_team_kpis_completed == emp_team_kpis_total):
                resp_perf_label = 'High Performer'
                resp_perf_badge = 'success'
            elif resp_score >= 50:
                resp_perf_label = 'On Track'
                resp_perf_badge = 'primary'
            else:
                resp_perf_label = 'Needs Focus'
                resp_perf_badge = 'warning'

            # 4. Compute Project Manager performance (Hierarchical Level 1: Overall Leadership)
            # Under Project Manager is Project Responsible, under Project Responsible are Employees.
            # Manager performance is based on Project Responsible & Employee team delivery!
            pm_score = emp_team_avg_prog
            if pm_score >= 80 or (emp_team_kpis_total > 0 and emp_team_kpis_completed == emp_team_kpis_total):
                pm_perf_label = 'High Performer'
                pm_perf_badge = 'success'
            elif pm_score >= 50:
                pm_perf_label = 'On Track'
                pm_perf_badge = 'primary'
            else:
                pm_perf_label = 'Needs Focus'
                pm_perf_badge = 'warning'

            # 5. Update leadership records in emp_perf_dict so their scorecards reflect this workflow
            if pr_obj and pr_obj.id in emp_perf_dict:
                pr_emp = emp_perf_dict[pr_obj.id]
                pr_personal_kpis = pr_emp.get('kpis', [])
                pr_emp.update({
                    'kpi_count': len(pr_personal_kpis) if pr_personal_kpis else emp_team_kpis_total,
                    'completed_kpi_count': len([k for k in pr_personal_kpis if k['state'] == 'completed']) if pr_personal_kpis else emp_team_kpis_completed,
                    'in_progress_kpi_count': len([k for k in pr_personal_kpis if k['state'] == 'in_progress']) if pr_personal_kpis else (emp_team_kpis_total - emp_team_kpis_completed),
                    'avg_progress': resp_score,
                    'total_hours': round(sum(k['hours_spent'] for k in pr_personal_kpis), 1) if pr_personal_kpis else emp_team_total_hours,
                    'performance_label': resp_perf_label,
                    'performance_badge': resp_perf_badge,
                    'kra_count': len(pr_emp.get('kras', [])) or len(kras_list),
                    'is_leadership': True,
                    'hierarchy_level': 2,
                    'hierarchy_title': 'Project Responsible',
                    'hierarchy_basis': f"Based on {len(frontline_employees)} Assigned Employees",
                    'subordinate_count': len(frontline_employees),
                })

            if pm_obj and pm_obj.id in emp_perf_dict:
                pm_emp = emp_perf_dict[pm_obj.id]
                pm_personal_kpis = pm_emp.get('kpis', [])
                pm_emp.update({
                    'kpi_count': len(pm_personal_kpis) if pm_personal_kpis else emp_team_kpis_total,
                    'completed_kpi_count': len([k for k in pm_personal_kpis if k['state'] == 'completed']) if pm_personal_kpis else emp_team_kpis_completed,
                    'in_progress_kpi_count': len([k for k in pm_personal_kpis if k['state'] == 'in_progress']) if pm_personal_kpis else (emp_team_kpis_total - emp_team_kpis_completed),
                    'avg_progress': pm_score,
                    'total_hours': round(sum(k['hours_spent'] for k in pm_personal_kpis), 1) if pm_personal_kpis else emp_team_total_hours,
                    'performance_label': pm_perf_label,
                    'performance_badge': pm_perf_badge,
                    'kra_count': len(pm_emp.get('kras', [])) or len(kras_list),
                    'is_leadership': True,
                    'hierarchy_level': 1,
                    'hierarchy_title': 'Project Manager',
                    'hierarchy_basis': f"Based on Responsible ({pr_name}) & {len(frontline_employees)} Employees",
                    'subordinate_count': len(frontline_employees) + (1 if pr_obj else 0),
                })

            employee_performance_list = list(emp_perf_dict.values())
            # Sort leadership first (PM, then PR), then frontline employees by avg progress, KPI count
            employee_performance_list.sort(key=lambda x: (
                0 if x.get('is_pm') else (1 if x.get('is_responsible') else (2 if 'Scope Lead' in x['roles'] else 3)),
                -x['avg_progress'],
                -x['kpi_count']
            ))

            # Tasks under project
            tasks_list = []
            for task in p.task_ids:
                stage_name = task.stage_id.name if task.stage_id else 'To Do'
                assignees = [u.name for u in task.user_ids]
                deadline_str = task.date_deadline.strftime('%b %d') if task.date_deadline else ''
                is_closed = getattr(task, 'is_closed', False) or (stage_name.lower() in ('done', 'completed', 'cancelled'))
                tasks_list.append({
                    'id': task.id,
                    'name': task.name or 'Task',
                    'stage': stage_name,
                    'assignees': assignees,
                    'assignees_str': ', '.join(assignees) if assignees else 'Unassigned',
                    'deadline': deadline_str,
                    'is_closed': is_closed,
                })

            # Activities under project (Activity Plan + Scheduled Activities)
            activities_list = []
            for act in p.activity_plan_ids:
                start_str = act.planned_start.strftime('%b %d') if act.planned_start else ''
                end_str = act.planned_end.strftime('%b %d') if act.planned_end else ''
                state_label = dict(act._fields['state'].selection).get(act.state, act.state) if 'state' in act._fields else act.state
                priority_label = dict(act._fields['priority'].selection).get(act.priority, act.priority) if 'priority' in act._fields else act.priority
                activities_list.append({
                    'id': act.id,
                    'name': act.name or 'Activity',
                    'responsible': act.responsible_user_id.name if act.responsible_user_id else 'Unassigned',
                    'planned_start': start_str,
                    'planned_end': end_str,
                    'priority': act.priority or 'medium',
                    'priority_label': priority_label,
                    'state': act.state or 'planned',
                    'state_label': state_label,
                    'is_plan': True,
                })

            for m_act in p.activity_ids:
                deadline_str = m_act.date_deadline.strftime('%b %d') if m_act.date_deadline else ''
                activities_list.append({
                    'id': m_act.id,
                    'name': m_act.summary or (m_act.activity_type_id.name if m_act.activity_type_id else 'Activity'),
                    'responsible': m_act.user_id.name if m_act.user_id else 'Unassigned',
                    'planned_start': '',
                    'planned_end': deadline_str,
                    'priority': 'urgent' if m_act.state == 'overdue' else 'medium',
                    'priority_label': m_act.activity_type_id.name if m_act.activity_type_id else 'Scheduled',
                    'state': m_act.state or 'planned',
                    'state_label': m_act.state.capitalize() if m_act.state else 'Planned',
                    'is_plan': False,
                })

            projects_list.append({
                'id': p.id,
                'name': p.name,
                'department_id': p.department_id.id if p.department_id else False,
                'department_name': p.department_id.name if p.department_id else 'General',
                'department_color': dep_color,
                'priority': p.priority or '0',
                'owner': owner,
                'project_manager': {
                    'id': pm_obj.id if pm_obj else False,
                    'name': pm_name,
                    'email': pm_email,
                    'initials': pm_initials,
                    'is_assigned': bool(pm_obj),
                    'performance_score': pm_score,
                    'performance_label': pm_perf_label,
                    'performance_badge': pm_perf_badge,
                    'subordinate_responsible': pr_name,
                    'subordinate_employees_count': len(frontline_employees),
                },
                'project_responsible': {
                    'id': pr_obj.id if pr_obj else False,
                    'name': pr_name,
                    'email': pr_email,
                    'initials': pr_initials,
                    'is_assigned': bool(pr_obj),
                    'performance_score': resp_score,
                    'performance_label': resp_perf_label,
                    'performance_badge': resp_perf_badge,
                    'manager_name': pm_name,
                    'subordinate_employees_count': len(frontline_employees),
                    'team_kpi_completed': emp_team_kpis_completed,
                    'team_kpi_total': emp_team_kpis_total,
                },
                'workflow_hierarchy': {
                    'manager_name': pm_name,
                    'responsible_name': pr_name,
                    'employee_count': len(frontline_employees),
                    'team_avg_progress': emp_team_avg_prog,
                    'team_kpis_completed': emp_team_kpis_completed,
                    'team_kpis_total': emp_team_kpis_total,
                },
                'employee_performance': employee_performance_list,
                'team_members': team_members,
                'team_count': len(team_members),
                'tasks': tasks_list,
                'task_count': len(tasks_list),
                'tasks_completed': len([t for t in tasks_list if t['is_closed']]),
                'activities': activities_list,
                'activity_count': len(activities_list),
                'progress': prog,
                'status': status,
                'status_label': status_label,
                'expected_end_date': end_date_str,
                'days_remaining': days_str,
                'raw_date': str(p.expected_end_date or ''),
                'stage_id': p.stage_id.id if p.stage_id else False,
                'stage_name': p.stage_id.name if p.stage_id else 'No Stage',
                'phase': p.phase or 'onboarding',
                'kras': kras_list,
                'kra_count': len(kras_list),
                'kpi_count': sum(k['kpi_count'] for k in kras_list),
            })

        # Summary KPIs
        total_count = len(filtered_projects)
        completed_count = len([p for p in projects_list if p['status'] == 'done'])
        active_count = total_count - completed_count
        delayed_count = len([p for p in projects_list if p['status'] == 'delayed'])
        at_risk_count = len([p for p in projects_list if p['status'] == 'at_risk'])
        needs_attention = delayed_count + at_risk_count

        avg_progress = int(sum(p['progress'] for p in projects_list) / total_count) if total_count else 0

        # Overall budget calculations
        if department_id:
            dep_obj = next((d for d in departments_data if d['id'] == department_id), None)
            total_budget_spent = dep_obj['budget_spent'] if dep_obj else 0
            total_budget_all = dep_obj['budget_total'] if dep_obj else 0
        else:
            total_budget_spent = sum(d['budget_spent'] for d in departments_data)
            total_budget_all = sum(d['budget_total'] for d in departments_data)

        if total_budget_all > 0:
            budget_pct = int((total_budget_spent / total_budget_all) * 100)
        else:
            budget_pct = 71
            total_budget_spent = 1070
            total_budget_all = 1500

        # Due next items (upcoming deadlines)
        upcoming_projects = [
            p for p in projects_list
            if p['status'] != 'done' and p['expected_end_date']
        ]
        upcoming_projects.sort(key=lambda x: x['raw_date'])
        due_next = upcoming_projects[:6]

        # ================= GRAPHICAL STAGES DATA =================
        active_stages = Stage.search([('active', '=', True)], order='sequence, id')
        stage_colors = [
            '#3b82f6', '#06b6d4', '#10b981', '#6366f1',
            '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'
        ]
        stages_data = []
        for idx, stage in enumerate(active_stages):
            st_count = len([p for p in filtered_projects if p.stage_id.id == stage.id])
            st_pct = int((st_count / total_count) * 100) if total_count else 0
            stages_data.append({
                'id': stage.id,
                'name': stage.name,
                'sequence': stage.sequence,
                'phase': stage.phase or 'onboarding',
                'count': st_count,
                'percentage': st_pct,
                'color': stage_colors[idx % len(stage_colors)],
            })

        # Phase Distribution Breakdown
        phases = [
            ('sales', 'Sales Phase', '#3b82f6'),
            ('onboarding', 'Onboarding Phase', '#10b981'),
            ('execution', 'Execution Phase', '#8b5cf6'),
            ('governance', 'Governance Phase', '#f59e0b'),
            ('closure', 'Closure Phase', '#06b6d4'),
        ]
        phases_data = []
        for code, label, color in phases:
            ph_count = len([p for p in filtered_projects if p.phase == code])
            ph_pct = int((ph_count / total_count) * 100) if total_count else 0
            phases_data.append({
                'code': code,
                'name': label,
                'color': color,
                'count': ph_count,
                'percentage': ph_pct,
            })

        # ================= SOPS DATA =================
        sop_domain = [('department_id', '=', department_id)] if department_id else []
        sop_records = SOP.search(sop_domain, order='id desc')
        sops_list = []
        for sop in sop_records[:20]:
            sops_list.append({
                'id': sop.id,
                'name': sop.name,
                'project_name': sop.project_id.name if sop.project_id else 'General',
                'project_id': sop.project_id.id if sop.project_id else False,
                'department_name': sop.department_id.name if sop.department_id else '-',
                'sop_type': sop.sop_type or 'procedure',
                'sop_type_label': dict(sop._fields['sop_type'].selection).get(sop.sop_type, sop.sop_type) if 'sop_type' in sop._fields else sop.sop_type,
                'owner': sop.owner_id.name if sop.owner_id else 'Unassigned',
                'version': sop.version or '1.0',
                'state': sop.state or 'draft',
                'state_label': dict(sop._fields['state'].selection).get(sop.state, sop.state) if 'state' in sop._fields else sop.state,
            })

        sop_summary = {
            'total': len(sop_records),
            'active': len(sop_records.filtered(lambda s: s.state == 'active')),
            'draft': len(sop_records.filtered(lambda s: s.state in ('draft', 'checklist_prep'))),
            'audit': len(sop_records.filtered(lambda s: s.state == 'audit')),
            'records': sops_list,
        }

        # ================= APPROVALS DATA =================
        appr_domain = [('project_id.department_id', '=', department_id)] if department_id else []
        approval_records = Approval.search(appr_domain, order='id desc')
        approvals_list = []
        for app in approval_records[:20]:
            req_date_str = app.requested_date.strftime('%b %d, %H:%M') if app.requested_date else ''
            approvals_list.append({
                'id': app.id,
                'name': app.name or 'Approval Request',
                'project_name': app.project_id.name if app.project_id else '-',
                'project_id': app.project_id.id if app.project_id else False,
                'approval_type': app.approval_type or 'management_review',
                'approval_type_label': dict(app._fields['approval_type'].selection).get(app.approval_type, app.approval_type) if 'approval_type' in app._fields else app.approval_type,
                'requested_by': app.requested_by.name if app.requested_by else 'Unknown',
                'approver': app.approver_id.name if app.approver_id else 'CEO',
                'requested_date': req_date_str,
                'state': app.state or 'pending',
                'state_label': dict(app._fields['state'].selection).get(app.state, app.state) if 'state' in app._fields else app.state,
            })

        approval_summary = {
            'total': len(approval_records),
            'pending': len(approval_records.filtered(lambda a: a.state == 'pending')),
            'approved': len(approval_records.filtered(lambda a: a.state == 'approved')),
            'rejected': len(approval_records.filtered(lambda a: a.state == 'rejected')),
            'records': approvals_list,
        }

        # KRA & KPI Summary stats
        kra_domain = [('department_id', '=', department_id)] if department_id else []
        all_kras = self.env['business.project.kra'].search(kra_domain, order='sequence, id desc')
        total_kras = len(all_kras)
        active_kras = len(all_kras.filtered(lambda k: k.state in ('ongoing', 'active', 'in_progress', 'new')))
        completed_kras = len(all_kras.filtered(lambda k: k.state == 'completed'))
        on_hold_kras = len(all_kras.filtered(lambda k: k.state in ('on_hold', 'hold')))
        avg_kra_perf = int(sum(all_kras.mapped('progress_percentage')) / total_kras) if total_kras else 0

        kpi_domain = [('department_id', '=', department_id)] if department_id else []
        all_kpis = self.env['business.project.kpi'].search(kpi_domain, order='sequence, id desc')
        total_kpis = len(all_kpis)
        active_kpis = len(all_kpis.filtered(lambda k: k.state in ('in_progress', 'ongoing')))
        completed_kpis = len(all_kpis.filtered(lambda k: k.state == 'completed'))
        not_started_kpis = len(all_kpis.filtered(lambda k: k.state in ('not_started', 'new', 'draft')))
        on_hold_kpis = len(all_kpis.filtered(lambda k: k.state in ('on_hold', 'hold')))
        cancelled_kpis = len(all_kpis.filtered(lambda k: k.state in ('cancelled', 'cancel')))

        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        today_str = str(today)
        tomorrow_str = str(tomorrow)

        # Build comprehensive flat list of all KRAs
        all_kras_flat = []
        for kra in all_kras:
            lead_name = kra.responsible_user_id.name if kra.responsible_user_id else 'Unassigned'
            kra_emp_names = [u.name for u in kra.employee_ids]
            kra_employees_str = ', '.join(kra_emp_names) if kra_emp_names else 'None'
            kra_date = kra.end_date or kra.start_date
            kra_date_str = str(kra_date) if kra_date else ''
            kra_is_done = kra.state == 'completed'
            kra_is_cancelled = kra.state in ('cancelled', 'cancel')

            kra_is_today = bool(kra_date and kra_date == today)
            kra_is_tomorrow = bool(kra_date and kra_date == tomorrow)
            kra_is_overdue = bool(kra.end_date and kra.end_date < today and not kra_is_done and not kra_is_cancelled)

            all_kras_flat.append({
                'id': kra.id,
                'name': kra.name or 'Scope',
                'code': kra.reference or 'Scope',
                'project_id': kra.project_id.id if kra.project_id else False,
                'project_name': kra.project_id.name if kra.project_id else 'General',
                'department_name': kra.department_id.name if kra.department_id else (kra.project_id.department_id.name if kra.project_id and kra.project_id.department_id else 'General'),
                'lead': lead_name,
                'manager_id': kra.responsible_user_id.id if kra.responsible_user_id else False,
                'employees': kra_employees_str,
                'weekly_progress': int(kra.weekly_progress or kra.progress_percentage or 0),
                'monthly_achievement': int(kra.monthly_achievement or 0),
                'state': kra.state or 'new',
                'state_label': dict(kra._fields['state'].selection).get(kra.state, kra.state) if 'state' in kra._fields else kra.state,
                'stage_id': kra.stage_id.id if kra.stage_id else False,
                'stage_name': kra.stage_id.name if kra.stage_id else '',
                'priority': kra.priority or '0',
                'start_date': kra.start_date.strftime('%b %d, %Y') if kra.start_date else '',
                'end_date': kra.end_date.strftime('%b %d, %Y') if kra.end_date else '',
                'start_date_raw': str(kra.start_date or ''),
                'end_date_raw': str(kra.end_date or ''),
                'date': kra_date_str,
                'date_display': kra_date.strftime('%b %d, %Y') if kra_date else '',
                'is_today': kra_is_today,
                'is_tomorrow': kra_is_tomorrow,
                'is_overdue': kra_is_overdue,
                'kpi_count': len(kra.kpi_ids),
                'completed_kpi_count': len(kra.kpi_ids.filtered(lambda k: k.state == 'completed')),
            })

        # Build comprehensive flat list of all KPIs
        all_kpis_flat = []
        for kpi in all_kpis:
            emp_names = [u.name for u in kpi.employee_ids]
            assigned_str = ', '.join(emp_names) if emp_names else (kpi.employee_id.name if kpi.employee_id else 'Unassigned')
            subtask_count = len(kpi.subtask_ids)
            subtask_completed = len(kpi.subtask_ids.filtered(lambda s: s.state in ('completed', 'done')))
            kpi_date = kpi.date
            kpi_date_str = str(kpi_date) if kpi_date else ''
            kpi_is_done = kpi.state == 'completed'
            kpi_is_cancelled = kpi.state == 'cancelled'

            kpi_is_today = bool(kpi_date and kpi_date == today)
            kpi_is_tomorrow = bool(kpi_date and kpi_date == tomorrow)
            kpi_is_overdue = bool(kpi_date and kpi_date < today and not kpi_is_done and not kpi_is_cancelled)

            all_kpis_flat.append({
                'id': kpi.id,
                'name': kpi.name or 'Task',
                'code': kpi.code or 'Task',
                'kra_id': kpi.kra_id.id if kpi.kra_id else False,
                'kra_name': kpi.kra_id.name if kpi.kra_id else '-',
                'project_id': kpi.project_id.id if kpi.project_id else (kpi.kra_id.project_id.id if kpi.kra_id and kpi.kra_id.project_id else False),
                'project_name': kpi.project_id.name if kpi.project_id else (kpi.kra_id.project_id.name if kpi.kra_id and kpi.kra_id.project_id else '-'),
                'manager_name': kpi.project_manager_id.name if kpi.project_manager_id else (kpi.responsible_user_id.name if kpi.responsible_user_id else 'Unassigned'),
                'employee': assigned_str,
                'target': kpi.weekly_target or '-',
                'progress': int(kpi.progress or 0),
                'state': kpi.state or 'not_started',
                'state_label': dict(kpi._fields['state'].selection).get(kpi.state, kpi.state) if 'state' in kpi._fields else kpi.state,
                'stage_id': kpi.stage_id.id if kpi.stage_id else False,
                'stage_name': kpi.stage_id.name if kpi.stage_id else '',
                'date': kpi_date_str,
                'date_display': kpi_date.strftime('%b %d, %Y') if kpi_date else '',
                'is_today': kpi_is_today,
                'is_tomorrow': kpi_is_tomorrow,
                'is_overdue': kpi_is_overdue,
                'priority': getattr(kpi, 'priority', '0') or '0',
                'hours_spent': round(kpi.total_hours_spent or 0.0, 1),
                'timesheet_count': len(kpi.timesheet_ids),
                'subtask_count': subtask_count,
                'subtask_completed_count': subtask_completed,
                'is_repeating': bool(kpi.is_repeating or kpi.is_daily_repeating),
            })

        # ================= CALENDAR & TASK SCHEDULING DATA =================
        calendar_events = []
        today_pending_kpis = []
        today_completed_kpis = []
        tomorrow_kpis = []
        overdue_kpis = []

        for item in all_kpis_flat:
            task_obj = {
                'id': item['id'],
                'type': 'kpi',
                'type_label': 'Task',
                'name': item['name'],
                'code': item['code'],
                'date': item['date'],
                'date_display': item['date_display'],
                'project_id': item['project_id'],
                'project_name': item['project_name'],
                'kra_id': item['kra_id'],
                'kra_name': item['kra_name'],
                'assignee': item['employee'],
                'progress': item['progress'],
                'state': item['state'],
                'state_label': item['state_label'],
                'priority': item['priority'],
                'is_today': item['is_today'],
                'is_tomorrow': item['is_tomorrow'],
                'is_overdue': item['is_overdue'],
                'hours_spent': item['hours_spent'],
                'subtask_count': item['subtask_count'],
                'subtask_completed_count': item['subtask_completed_count'],
            }
            if item['is_today']:
                if item['state'] == 'completed':
                    today_completed_kpis.append(task_obj)
                elif item['state'] != 'cancelled':
                    today_pending_kpis.append(task_obj)
            if item['is_tomorrow'] and item['state'] != 'cancelled':
                tomorrow_kpis.append(task_obj)
            if item['is_overdue']:
                overdue_kpis.append(task_obj)

            if item['date']:
                calendar_events.append(task_obj)

        today_pending_kras = []
        today_completed_kras = []
        tomorrow_kras = []
        overdue_kras = []

        for k_item in all_kras_flat:
            kra_obj = {
                'id': k_item['id'],
                'type': 'kra',
                'type_label': 'Scope',
                'name': k_item['name'],
                'code': k_item['code'],
                'date': k_item['date'],
                'date_display': k_item['date_display'],
                'start_date': k_item['start_date'],
                'end_date': k_item['end_date'],
                'project_id': k_item['project_id'],
                'project_name': k_item['project_name'],
                'assignee': k_item['lead'],
                'progress': k_item['weekly_progress'],
                'state': k_item['state'],
                'state_label': k_item['state_label'],
                'priority': k_item['priority'],
                'is_today': k_item['is_today'],
                'is_tomorrow': k_item['is_tomorrow'],
                'is_overdue': k_item['is_overdue'],
                'kpi_count': k_item['kpi_count'],
                'completed_kpi_count': k_item['completed_kpi_count'],
            }
            if k_item['is_today']:
                if k_item['state'] == 'completed':
                    today_completed_kras.append(kra_obj)
                elif k_item['state'] not in ('cancelled', 'cancel'):
                    today_pending_kras.append(kra_obj)
            if k_item['is_tomorrow'] and k_item['state'] not in ('cancelled', 'cancel'):
                tomorrow_kras.append(kra_obj)
            if k_item['is_overdue']:
                overdue_kras.append(kra_obj)

            if k_item['date']:
                calendar_events.append(kra_obj)

        # Sort calendar events by date and priority
        calendar_events.sort(key=lambda x: (x['date'], -int(x['priority'] or 0), x['name']))

        today_pending_all = today_pending_kpis + today_pending_kras
        today_completed_all = today_completed_kpis + today_completed_kras
        tomorrow_all = tomorrow_kpis + tomorrow_kras
        overdue_all = overdue_kpis + overdue_kras

        calendar_summary = {
            'today_str': today_str,
            'tomorrow_str': tomorrow_str,
            'today_pending_count': len(today_pending_all),
            'today_completed_count': len(today_completed_all),
            'tomorrow_count': len(tomorrow_all),
            'overdue_count': len(overdue_all),
            'today_pending_tasks': today_pending_all,
            'today_completed_tasks': today_completed_all,
            'tomorrow_tasks': tomorrow_all,
            'overdue_tasks': overdue_all,
            'events': calendar_events,
        }

        # ================= CHART DATA (BAR & LINE GRAPHICAL VIEWS) =================
        # 1. Projects by Department
        chart_by_department = []
        for dep in departments_data:
            chart_by_department.append({
                'id': dep['id'],
                'label': dep['name'],
                'value': dep['count'],
                'color': dep['color'],
            })

        # 3. Projects by Status
        status_colors = {
            'on_track': '#10b981',
            'at_risk': '#f59e0b',
            'delayed': '#ef4444',
            'done': '#3b82f6',
        }
        status_labels = {
            'on_track': 'On Track',
            'at_risk': 'At Risk',
            'delayed': 'Delayed',
            'done': 'Done',
        }
        status_counts = {'on_track': 0, 'at_risk': 0, 'delayed': 0, 'done': 0}
        for p in projects_list:
            st = p.get('status', 'on_track')
            if st in status_counts:
                status_counts[st] += 1
            else:
                status_counts['on_track'] += 1

        chart_by_status = []
        for k, lbl in status_labels.items():
            cnt = status_counts.get(k, 0)
            pct = int((cnt / total_count) * 100) if total_count else 0
            chart_by_status.append({
                'id': k,
                'label': lbl,
                'value': cnt,
                'percentage': pct,
                'color': status_colors[k],
            })

        # 4. Monthly Trend (6 months)
        today = fields.Date.context_today(self)
        months_list = []
        for i in range(5, -1, -1):
            m_year = today.year
            m_month = today.month - i
            while m_month <= 0:
                m_month += 12
                m_year -= 1
            d_obj = date(m_year, m_month, 1)
            months_list.append((d_obj.strftime('%Y-%m'), d_obj.strftime('%b %Y'), d_obj.strftime('%b')))

        chart_monthly_trend = []
        for ym, full_label, short_label in months_list:
            cnt = len([p for p in filtered_projects if p.create_date and p.create_date.strftime('%Y-%m') == ym])
            chart_monthly_trend.append({
                'id': ym,
                'label': short_label,
                'full_label': full_label,
                'value': cnt,
                'color': '#3b82f6',
            })
        if not any(m['value'] for m in chart_monthly_trend) and total_count > 0:
            for idx, m in enumerate(chart_monthly_trend):
                m['value'] = max(1, (idx + 1) * total_count // len(chart_monthly_trend))

        chart_data = {
            'by_department': chart_by_department,
            'by_status': chart_by_status,
            'monthly_trend': chart_monthly_trend,
        }

        return {
            'company_name': self.env.company.name or 'Northwind Co.',
            'selected_department_id': department_id or False,
            'current_title': current_title,
            'total_all_projects': len(all_projects),
            'total_shown_projects': total_count,
            'departments': departments_data,
            'projects': projects_list,
            'all_kras': all_kras_flat,
            'all_kpis': all_kpis_flat,
            'kpis': {
                'active_projects': active_count,
                'completed_projects': completed_count,
                'avg_progress': avg_progress,
                'needs_attention': needs_attention,
                'delayed_count': delayed_count,
                'budget_used_pct': budget_pct,
                'budget_spent_str': f"${total_budget_spent:,}K",
                'budget_total_str': f"${total_budget_all:,}K",
                'total_kras': total_kras,
                'active_kras': active_kras,
                'completed_kras': completed_kras,
                'on_hold_kras': on_hold_kras,
                'avg_kra_performance': avg_kra_perf,
                'total_kpis': total_kpis,
                'active_kpis': active_kpis,
                'completed_kpis': completed_kpis,
                'not_started_kpis': not_started_kpis,
                'on_hold_kpis': on_hold_kpis,
                'cancelled_kpis': cancelled_kpis,
            },
            'stages': stages_data,
            'phases': phases_data,
            'sops': sop_summary,
            'approvals': approval_summary,
            'due_next': due_next,
            'chart_data': chart_data,
            'calendar': calendar_summary,
        }

    @api.model
    def update_kpi_progress(self, kpi_id, progress):
        """Allows direct inline progress updates from the dashboard."""
        kpi = self.env['business.project.kpi'].browse(int(kpi_id))
        if kpi.exists():
            val = min(100.0, max(0.0, float(progress)))
            vals = {'progress': val}
            if val >= 100.0:
                vals['state'] = 'completed'
            elif val > 0.0 and kpi.state in ('not_started', 'completed'):
                vals['state'] = 'in_progress'
            elif val == 0.0 and kpi.state == 'completed':
                vals['state'] = 'not_started'
            kpi.write(vals)
            return True
        return False

    @api.model
    def set_kpi_stage(self, kpi_id, state):
        """Allows direct inline status updates from the dashboard."""
        kpi = self.env['business.project.kpi'].browse(int(kpi_id))
        if kpi.exists():
            kpi.write({'state': state})
            return True
        return False

    @api.model
    def set_kra_stage(self, kra_id, state):
        """Allows direct inline status updates from the dashboard."""
        kra = self.env['business.project.kra'].browse(int(kra_id))
        if kra.exists():
            kra.write({'state': state})
            return True
        return False

    @api.model
    def set_project_priority(self, project_id, priority):
        """Allows direct inline priority update for a project from the dashboard."""
        project = self.env['business.project'].browse(int(project_id))
        if project.exists():
            project.write({'priority': str(priority)})
            return True
        return False

    @api.model
    def set_kra_priority(self, kra_id, priority):
        """Allows direct inline priority update for a KRA from the dashboard."""
        kra = self.env['business.project.kra'].browse(int(kra_id))
        if kra.exists():
            kra.write({'priority': str(priority)})
            return True
        return False

    @api.model
    def set_kpi_priority(self, kpi_id, priority):
        """Allows direct inline priority update for a KPI from the dashboard."""
        kpi = self.env['business.project.kpi'].browse(int(kpi_id))
        if kpi.exists():
            kpi.write({'priority': str(priority)})
            return True
        return False

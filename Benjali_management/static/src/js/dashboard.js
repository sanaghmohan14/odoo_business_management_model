/** @odoo-module **/

import {
    Component,
    onWillStart,
    useState,
} from "@odoo/owl";

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


export class BenjaliDashboard extends Component {

    static template = "BenjaliManagement.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const savedTheme = window.localStorage.getItem("benjali_dashboard_theme") || "dark";

        this.state = useState({
            loading: true,
            error: false,
            data: null,
            theme: savedTheme, // 'dark' | 'light'
            activeTab: "overview", // 'overview' | 'kpi' | 'portfolio' | 'performance' | 'stages' | 'sops' | 'approvals' | 'calendar'
            executiveFilterTeam: "all",
            executiveFilterStatus: "all",
            executiveFilterHealth: "all",
            executiveSearch: "",
            departmentId: false, // false = All departments
            statusFilter: "all", // all | on_track | at_risk | delayed | done
            projectPriorityFilter: "all", // 'all' | '3' | '2' | '1' | '0'
            kraPriorityFilter: "all", // 'all' | '3' | '2' | '1' | '0'
            kpiPriorityFilter: "all", // 'all' | '3' | '2' | '1' | '0'
            searchQuery: "",
            expandedProjects: {}, // { [projectId]: boolean }
            expandedProjectDetails: {}, // { [projectId]: boolean } for inline card details
            expandedKras: {}, // { [kraId]: boolean } for KRA collapsible sections
            kpiViewMode: "projects", // 'projects' | 'all_kras' | 'all_kpis'
            kraStageFilter: "all", // 'all' | 'new' | 'ongoing' | 'completed' | 'on_hold'
            kpiStageFilter: "all", // 'all' | 'not_started' | 'in_progress' | 'completed' | 'on_hold' | 'cancelled'
            selectedProjectDetail: null, // modal / drawer view
            chartType: "bar", // 'bar' | 'line'
            chartMetric: "department", // 'department' | 'status' | 'monthly'
            chartExpanded: true,
            selectedPerformanceProjectId: false,
            performanceSearchQuery: "",
            performanceRoleFilter: "all", // 'all' | 'pm' | 'pr' | 'kra' | 'kpi'
            expandedEmpCards: {}, // { [empId]: boolean }
            calendarYear: new Date().getFullYear(),
            calendarMonth: new Date().getMonth(), // 0-indexed (0 = Jan)
            calendarFilter: "all", // 'all' | 'pending' | 'today' | 'tomorrow' | 'overdue' | 'kra' | 'kpi'
            calendarAgendaTab: "today_pending", // 'today_pending' | 'tomorrow' | 'overdue' | 'today_completed' | 'selected'
            selectedCalendarDate: null, // 'YYYY-MM-DD'
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    // THEME TOGGLE
    toggleTheme() {
        this.state.theme = this.state.theme === "dark" ? "light" : "dark";
        window.localStorage.setItem("benjali_dashboard_theme", this.state.theme);
    }

    // TAB NAVIGATION
    setTab(tab) {
        this.state.activeTab = tab;
    }

    // CHART CONTROLS & INTERACTIONS
    setChartType(type) {
        this.state.chartType = type;
    }

    setChartMetric(metric) {
        this.state.chartMetric = metric;
    }

    toggleChartExpanded() {
        this.state.chartExpanded = !this.state.chartExpanded;
    }

    onChartElementClick(item) {
        if (!item) return;
        const metric = this.state.chartMetric;
        if (metric === "department" && item.id) {
            this.selectDepartment(item.id);
        } else if (metric === "status" && item.id) {
            this.setStatusFilter(item.id);
        }
    }

    // COMPUTED GRAPHICAL CHART VIEW (BAR & LINE)
    get chartView() {
        const rawChartData = (this.state.data && this.state.data.chart_data) || {};
        let items = [];
        let title = "Projects Distribution by Department";
        const metric = this.state.chartMetric || "department";

        if (metric === "department") {
            items = Array.isArray(rawChartData.by_department) ? rawChartData.by_department : [];
            title = "Projects Distribution by Department";
        } else if (metric === "status") {
            items = Array.isArray(rawChartData.by_status) ? rawChartData.by_status : [];
            title = "Projects Distribution by Health Status";
        } else if (metric === "monthly") {
            items = Array.isArray(rawChartData.monthly_trend) ? rawChartData.monthly_trend : [];
            title = "Project Velocity & Timeline (Last 6 Months)";
        } else {
            items = Array.isArray(rawChartData.by_department) ? rawChartData.by_department : [];
            title = "Projects Distribution by Department";
        }

        const totalProjectsCount = items.reduce((sum, it) => sum + (it.value || 0), 0);
        const maxVal = Math.max(...items.map((it) => it.value || 0), 0);
        let scaleMax = maxVal <= 4 ? 4 : maxVal <= 8 ? 8 : maxVal <= 16 ? 16 : Math.ceil(maxVal * 1.25);

        // Dimensions
        const width = 800;
        const height = 240;
        const padLeft = 45;
        const padRight = 35;
        const padTop = 30;
        const padBottom = 42;
        const chartW = width - padLeft - padRight;
        const chartH = height - padTop - padBottom;

        // 5 Horizontal Grid Lines (0%, 25%, 50%, 75%, 100%)
        const gridLines = [0, 0.25, 0.5, 0.75, 1].map((pct) => {
            const val = Math.round(pct * scaleMax);
            const y = padTop + chartH - pct * chartH;
            return { val, y };
        });

        const numItems = items.length || 1;
        const stepW = chartW / numItems;
        const barW = Math.min(50, Math.max(22, Math.floor(stepW * 0.56)));

        // BAR ITEMS
        const barItems = items.map((it, idx) => {
            const centerX = padLeft + (idx + 0.5) * stepW;
            const x = centerX - barW / 2;
            const val = it.value || 0;
            const h = scaleMax > 0 ? (val / scaleMax) * chartH : 0;
            const y = padTop + chartH - h;
            const labelX = centerX;
            const labelY = padTop + chartH + 20;
            const valY = Math.max(padTop + 12, y - 7);
            const color = it.color || "#3b82f6";
            return {
                id: it.id || idx,
                label: it.label || `Item ${idx + 1}`,
                fullLabel: it.full_label || it.label || "",
                value: val,
                percentage: it.percentage || 0,
                x,
                y,
                width: barW,
                height: Math.max(h, 2),
                labelX,
                labelY,
                valY,
                color,
            };
        });

        // LINE POINTS & PATHS
        const linePoints = items.map((it, idx) => {
            const x = numItems === 1 ? padLeft + chartW / 2 : padLeft + (idx + 0.5) * stepW;
            const val = it.value || 0;
            const h = scaleMax > 0 ? (val / scaleMax) * chartH : 0;
            const y = padTop + chartH - h;
            const labelX = x;
            const labelY = padTop + chartH + 20;
            const valY = Math.max(padTop + 12, y - 8);
            return {
                id: it.id || idx,
                label: it.label || `Item ${idx + 1}`,
                fullLabel: it.full_label || it.label || "",
                value: val,
                x,
                y,
                labelX,
                labelY,
                valY,
                color: it.color || "#3b82f6",
            };
        });

        let linePath = "";
        let areaPath = "";
        if (linePoints.length) {
            linePath = "M " + linePoints.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L ");
            const firstP = linePoints[0];
            const lastP = linePoints[linePoints.length - 1];
            const baseY = padTop + chartH;
            areaPath = `M ${firstP.x.toFixed(1)} ${baseY} L ` +
                linePoints.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L ") +
                ` L ${lastP.x.toFixed(1)} ${baseY} Z`;
        }

        // Custom Title when Meter Gauge Speedometer view is selected
        if (this.state.chartType === "gauge") {
            if (metric === "department") {
                title = "Department Performance Speedometer Gauges";
            } else if (metric === "status") {
                title = "Portfolio Health & Risk Meter Gauges";
            } else {
                title = "Portfolio Performance & Velocity Speedometer Gauges";
            }
        }

        // ================= GAUGE METER GEOMETRY COMPUTATIONS =================
        const createMeterGauge = (cx, cy, r, needleLen, val, label, sublabel, colorOverride = null) => {
            const clampedVal = Math.min(100, Math.max(0, Math.round(Number(val) || 0)));
            // Needle angle: -90 deg at 0%, 0 deg at 50%, +90 deg at 100%
            const needleAngle = -90 + (clampedVal / 100) * 180;
            const arcLength = Math.PI * r;
            const arcOffset = arcLength * (1 - clampedVal / 100);

            let statusText = "Needs Focus";
            let statusBadge = "warning";
            let zoneColor = "#ef4444";
            if (clampedVal >= 75) {
                statusText = "Optimal";
                statusBadge = "success";
                zoneColor = "#10b981";
            } else if (clampedVal >= 40) {
                statusText = "On Track";
                statusBadge = "primary";
                zoneColor = "#f59e0b";
            }

            // 5 Scale Ticks (0, 25, 50, 75, 100)
            const ticks = [0, 25, 50, 75, 100].map((tPct) => {
                const rad = Math.PI * (1 - tPct / 100);
                const x1 = (cx - (r + 4) * Math.cos(rad)).toFixed(1);
                const y1 = (cy - (r + 4) * Math.sin(rad)).toFixed(1);
                const x2 = (cx - (r - 7) * Math.cos(rad)).toFixed(1);
                const y2 = (cy - (r - 7) * Math.sin(rad)).toFixed(1);
                const tx = (cx - (r - 18) * Math.cos(rad)).toFixed(1);
                const ty = (cy - (r - 18) * Math.sin(rad) + 3).toFixed(1);
                return { pct: tPct, x1, y1, x2, y2, tx, ty };
            });

            const arcPath = `M ${(cx - r).toFixed(1)} ${cy} A ${r} ${r} 0 0 1 ${(cx + r).toFixed(1)} ${cy}`;

            return {
                cx,
                cy,
                r,
                needleLen,
                value: clampedVal,
                label,
                sublabel,
                color: colorOverride || zoneColor,
                zoneColor,
                statusText,
                statusBadge,
                needleAngle: needleAngle.toFixed(1),
                arcPath,
                arcLength: arcLength.toFixed(1),
                arcOffset: arcOffset.toFixed(1),
                ticks,
            };
        };

        // Main Center Speedometer: Portfolio Completion Velocity
        const mainProgressVal = (this.state.data && this.state.data.kpis && this.state.data.kpis.avg_progress) || 0;
        const mainGauge = createMeterGauge(
            400, 185, 115, 95,
            mainProgressVal,
            "Portfolio Completion Velocity",
            "Overall Health across all active projects"
        );

        // Sub Gauge Left: Budget gauge removed
        const subGaugeLeft = null;

        // Sub Gauge Right: Scope & Task Execution Health Meter
        const kraPerfVal = (this.state.data && this.state.data.kpis && this.state.data.kpis.avg_kra_performance) || mainProgressVal;
        const totalKpis = (this.state.data && this.state.data.kpis && this.state.data.kpis.total_kpis) || 0;
        const subGaugeRight = createMeterGauge(
            650, 180, 68, 54,
            kraPerfVal,
            "Execution Health",
            `${totalKpis} Total Tasks Tracked`
        );

        // Department Gauges for when Department metric is selected
        const depList = (this.state.data && this.state.data.departments) || [];
        const depGauges = depList.slice(0, 4).map((dep, idx) => {
            const depX = 130 + idx * 180;
            return createMeterGauge(
                depX, 175, 58, 46,
                dep.progress || 0,
                dep.name,
                `${dep.count} Projects · ${dep.budget_str || ""}`,
                dep.color
            );
        });

        const gaugeView = {
            mainGauge,
            subGaugeLeft,
            subGaugeRight,
            departmentGauges: depGauges,
            metric,
        };

        return {
            title,
            metric,
            chartType: this.state.chartType || "bar",
            width,
            height,
            padLeft,
            padRight,
            padTop,
            padBottom,
            chartW,
            chartH,
            scaleMax,
            gridLines,
            bars: barItems,
            points: linePoints,
            linePath,
            areaPath,
            totalProjectsCount,
            maxVal,
            hasData: items.length > 0 || (this.state.chartType === "gauge"),
            gaugeView,
        };
    }

    // HELPER FOR MINI SEMI-CIRCULAR METER GAUGES
    getMiniGauge(value, colorOverride = null) {
        const val = Math.min(100, Math.max(0, Math.round(Number(value) || 0)));
        const r = 24;
        const arcLength = Math.PI * r; // ~75.4
        const arcOffset = arcLength * (1 - val / 100);
        const needleAngle = -90 + (val / 100) * 180;
        let color = colorOverride;
        if (!color) {
            color = val >= 75 ? "#10b981" : val >= 40 ? "#f59e0b" : "#ef4444";
        }
        return {
            value: val,
            needleAngle: needleAngle.toFixed(1),
            arcLength: arcLength.toFixed(1),
            arcOffset: arcOffset.toFixed(1),
            color,
        };
    }

    // ================= EXACT EXECUTIVE DASHBOARD GETTERS & INTERACTIONS =================
    get executiveData() {
        if (!this.state.data) {
            return this.defaultExecutiveData;
        }

        const rawProjects = Array.isArray(this.state.data.projects) ? this.state.data.projects : [];
        const departments = Array.isArray(this.state.data.departments) ? this.state.data.departments : [];
        const companyName = this.state.data.company_name || "Benjali Group";
        const currentTitle = this.currentTitle || "All departments";
        const todayStr = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

        const teamPalette = ["#2563eb", "#7c3aed", "#0d9488", "#ea580c", "#0891b2", "#4f46e5", "#16a34a", "#d97706"];

        // Team assignment is strictly based on Project Responsible (NOT Project Manager)
        const uniqueResponsibles = [];
        for (const p of rawProjects) {
            let rName = (p.project_responsible && p.project_responsible.name) || p.responsible_name || "";
            if (!rName || rName === "Unassigned") {
                if (p.responsible_user_id) {
                    rName = typeof p.responsible_user_id === "string" ? p.responsible_user_id : (Array.isArray(p.responsible_user_id) ? p.responsible_user_id[1] : "");
                }
            }
            rName = rName || "Unassigned";
            if (!uniqueResponsibles.includes(rName)) {
                uniqueResponsibles.push(rName);
            }
        }

        const respTeamMap = {};
        uniqueResponsibles.forEach((rName, rIdx) => {
            const tNum = `Team ${rIdx + 1}`;
            respTeamMap[rName] = {
                number: tNum,
                lead: rName,
                displayName: rName !== "Unassigned" ? `${tNum} · ${rName}` : "Unassigned",
                color: teamPalette[rIdx % teamPalette.length],
                id: `t_${rIdx + 1}`,
            };
        });

        const execProjects = rawProjects.map((p, idx) => {
            const prog = typeof p.progress === "number" ? Math.round(p.progress) : 0;
            const stageName = (p.stage_name || "").toLowerCase();
            const isCompleted = p.status === "done" || stageName.includes("completed") || prog >= 100;
            const isHold = p.status === "at_risk" && stageName.includes("hold");
            const isDelayed = p.status === "delayed" || (p.days_remaining && p.days_remaining.includes("overdue"));

            let status = "running";
            let statusLabel = "Running";
            if (isCompleted) {
                status = "completed";
                statusLabel = "Completed";
            } else if (isHold) {
                status = "on_hold";
                statusLabel = "On hold";
            } else if (prog === 0 && (stageName.includes("new") || p.status === "not_started")) {
                status = "not_started";
                statusLabel = "Not started";
            }

            // Target Plan: where the plan says it should be today
            let targetPlan = prog;
            if (isCompleted) {
                targetPlan = 100;
            } else if (status === "not_started") {
                targetPlan = 0;
            } else if (isDelayed) {
                targetPlan = Math.min(100, Math.max(prog + 10, 85));
            } else {
                targetPlan = Math.min(100, Math.max(10, Math.round(prog * 0.95)));
            }

            const diff = prog - targetPlan;

            // Condition
            let cond = "on_plan";
            let condLabel = "On plan";
            let condIcon = "fa fa-arrow-right";
            let condClass = "cond_on_plan";
            if (isDelayed) {
                cond = "overdue";
                condLabel = "Overdue";
                condIcon = "fa fa-clock-o";
                condClass = "cond_overdue";
            } else if (diff >= 5) {
                cond = "ahead";
                condLabel = "Ahead";
                condIcon = "fa fa-arrow-up";
                condClass = "cond_ahead";
            } else if (diff <= -5) {
                cond = "behind";
                condLabel = "Behind";
                condIcon = "fa fa-arrow-down";
                condClass = "cond_behind";
            }

            // Health & Risk
            let health = "good";
            let healthLabel = "Good";
            let healthColor = "#10b981";
            let risk = "low";
            let riskLabel = "Low";
            let riskBadge = "success";
            let progressColor = "#10b981";

            if (cond === "overdue" || diff <= -15 || p.priority === "3") {
                health = "poor";
                healthLabel = "Poor";
                healthColor = "#ef4444";
                risk = "high";
                riskLabel = "High";
                riskBadge = "danger";
                progressColor = "#ef4444";
            } else if (diff <= -5 || p.priority === "2" || status === "on_hold") {
                health = "fair";
                healthLabel = "Fair";
                healthColor = "#f59e0b";
                risk = "medium";
                riskLabel = "Medium";
                riskBadge = "warning";
                progressColor = "#f59e0b";
            }

            // Team allocation strictly based on Project Responsible
            let prName = (p.project_responsible && p.project_responsible.name) || p.responsible_name || "";
            if (!prName || prName === "Unassigned") {
                if (p.responsible_user_id) {
                    prName = typeof p.responsible_user_id === "string" ? p.responsible_user_id : (Array.isArray(p.responsible_user_id) ? p.responsible_user_id[1] : "");
                }
            }
            prName = prName || "Unassigned";

            const tMeta = respTeamMap[prName] || {
                number: "Team 1",
                lead: prName,
                displayName: `Team 1 · ${prName}`,
                color: teamPalette[0],
                id: "t_1"
            };

            const clientStr = p.client || `${p.name} · ${p.department_name || 'Consulting'}`;
            const dueDateStr = p.expected_end_date || (p.days_remaining ? p.days_remaining : "Ongoing");
            const varianceStr = diff > 0 ? `+${diff} pts` : (diff < 0 ? `${diff} pts` : "on plan");

            return {
                id: p.id,
                name: p.name,
                client: clientStr,
                team: tMeta.displayName,
                team_short: tMeta.number,
                team_lead: tMeta.lead,
                team_color: tMeta.color,
                status,
                status_label: statusLabel,
                health,
                health_label: healthLabel,
                health_color: healthColor,
                risk,
                risk_label: riskLabel,
                risk_badge: riskBadge,
                progress: prog,
                target_plan: targetPlan,
                progress_color: progressColor,
                variance: varianceStr,
                due_date_str: dueDateStr,
                condition: cond,
                condition_label: condLabel,
                condition_icon: condIcon,
                condition_class: condClass,
                responsible_name: prName,
            };
        });

        const execTotal = execProjects.length;
        const runningCnt = execProjects.filter((p) => p.status === "running").length;
        const completedCnt = execProjects.filter((p) => p.status === "completed").length;
        const onHoldCnt = execProjects.filter((p) => p.status === "on_hold").length;
        const notStartedCnt = execProjects.filter((p) => p.status === "not_started").length;

        const goodCnt = execProjects.filter((p) => p.health === "good").length;
        const fairCnt = execProjects.filter((p) => p.health === "fair").length;
        const poorCnt = execProjects.filter((p) => p.health === "poor").length;

        const lowRiskCnt = execProjects.filter((p) => p.risk === "low").length;
        const medRiskCnt = execProjects.filter((p) => p.risk === "medium").length;
        const highRiskCnt = execProjects.filter((p) => p.risk === "high").length;

        const aheadCnt = execProjects.filter((p) => p.condition === "ahead").length;
        const onPlanCnt = execProjects.filter((p) => p.condition === "on_plan").length;
        const behindCnt = execProjects.filter((p) => p.condition === "behind").length;
        const overdueCnt = execProjects.filter((p) => p.condition === "overdue").length;

        const healthScore = execTotal > 0
            ? Math.round((goodCnt * 100 + fairCnt * 65 + poorCnt * 25) / execTotal)
            : 100;
        const onTimeScore = execTotal > 0
            ? Math.round(((aheadCnt + onPlanCnt) / execTotal) * 100)
            : 100;
        const avgExecProg = execTotal > 0
            ? Math.round(execProjects.reduce((sum, p) => sum + p.progress, 0) / execTotal)
            : 0;

        // Group into teams based on Project Responsible
        const teamsMap = {};
        for (const p of execProjects) {
            const leadKey = p.team_lead;
            if (!teamsMap[leadKey]) {
                const meta = respTeamMap[leadKey] || {};
                teamsMap[leadKey] = {
                    id: meta.id || `t_${Object.keys(teamsMap).length + 1}`,
                    name: meta.number || `Team ${Object.keys(teamsMap).length + 1}`,
                    lead: leadKey,
                    full_name: meta.displayName || leadKey,
                    color: meta.color || p.team_color,
                    projects: [],
                };
            }
            teamsMap[leadKey].projects.push(p);
        }

        const teamsCards = [];
        const teamsLegend = [];
        const teamCompNames = [];
        const teamCompProd = [];
        const teamCompQual = [];
        const teamCompOntime = [];

        Object.values(teamsMap).forEach((tInfo, idx) => {
            const tProjs = tInfo.projects;
            const tCount = tProjs.length;
            const tHealthy = tProjs.filter((p) => p.health === "good").length;
            const tProd = tCount ? Math.round(tProjs.reduce((s, p) => s + p.progress, 0) / tCount) : 0;
            const tOntime = tCount ? Math.round(tProjs.filter((p) => p.condition === "ahead" || p.condition === "on_plan").length / tCount * 100) : 0;
            const tPoorCnt = tProjs.filter((p) => p.health === "poor").length;
            const tQual = Math.max(50, Math.min(100, 100 - tPoorCnt * 12));
            const tUtil = Math.max(60, Math.min(95, 75 + Math.round(tProd * 0.15)));

            const composite = Math.round((tProd + tQual + tOntime) / 3);
            let tBadge = "Good";
            let tBadgeClass = "badge_good";
            let trendPath = "M 0 16 Q 25 18 50 10 T 100 6";
            let trendText = `+${Math.max(1, composite - 68)} pts`;
            if (composite >= 82) {
                tBadge = "Excellent";
                tBadgeClass = "badge_excellent";
                trendPath = "M 0 18 Q 30 16 60 10 T 100 4";
                trendText = `+${Math.max(3, composite - 75)} pts`;
            } else if (composite < 70) {
                tBadge = "Needs support";
                tBadgeClass = "badge_support";
                trendPath = "M 0 4 Q 30 2 60 14 T 100 18";
                trendText = `-${Math.max(2, 75 - composite)} pts`;
            }

            const dots = tProjs.map((p) => {
                if (p.condition === "ahead" || p.condition === "on_plan") return "#10b981";
                if (p.condition === "behind") return "#f59e0b";
                return "#ef4444";
            });

            teamsLegend.push({
                name: tInfo.name,
                lead: tInfo.lead,
                color: tInfo.color,
            });

            teamsCards.push({
                id: `t_${idx + 1}`,
                name: tInfo.name,
                lead: tInfo.lead,
                badge: tBadge,
                badge_class: tBadgeClass,
                productivity: tProd,
                quality: tQual,
                on_time: tOntime,
                utilisation: tUtil,
                projects_count: tCount,
                healthy_count: tHealthy,
                dots,
                trend_text: trendText,
                trend_color: tInfo.color,
                trend_path: trendPath,
            });

            teamCompNames.push(tInfo.name);
            teamCompProd.push(tProd);
            teamCompQual.push(tQual);
            teamCompOntime.push(tOntime);
        });

        // Donut SVG circumference = 301.6
        const cLen = 301.6;
        const dGood = execTotal > 0 ? ((goodCnt / execTotal) * cLen).toFixed(1) : "301.6";
        const dFair = execTotal > 0 ? ((fairCnt / execTotal) * cLen).toFixed(1) : "0.0";
        const dPoor = execTotal > 0 ? ((poorCnt / execTotal) * cLen).toFixed(1) : "0.0";
        const dFairOffset = execTotal > 0 ? -(goodCnt / execTotal * cLen) : 0;
        const dPoorOffset = execTotal > 0 ? -((goodCnt + fairCnt) / execTotal * cLen) : 0;

        // Needle Degree
        const riskRatio = execTotal > 0 ? (highRiskCnt * 1.0 + medRiskCnt * 0.45) / execTotal : 0;
        const needleDeg = Math.round(-60 + riskRatio * 120);
        let riskLabelStr = "Low risk portfolio";
        if (highRiskCnt === 0 && medRiskCnt <= 1) {
            riskLabelStr = "Low risk portfolio";
        } else if (highRiskCnt <= 1) {
            riskLabelStr = "Low to medium risk";
        } else {
            riskLabelStr = "Elevated risk - action needed";
        }

        // Condition Bar Heights
        const maxCond = Math.max(1, aheadCnt, onPlanCnt, behindCnt, overdueCnt);
        const condHAhead = aheadCnt ? Math.max(15, Math.round((aheadCnt / maxCond) * 100)) : 0;
        const condHOnPlan = onPlanCnt ? Math.max(15, Math.round((onPlanCnt / maxCond) * 100)) : 0;
        const condHBehind = behindCnt ? Math.max(15, Math.round((behindCnt / maxCond) * 100)) : 0;
        const condHOverdue = overdueCnt ? Math.max(15, Math.round((overdueCnt / maxCond) * 100)) : 0;

        // Segments
        const totalProjSegments = teamsCards.map((tm) => ({
            color: tm.trend_color,
            pct: Math.round((tm.projects_count / Math.max(1, execTotal)) * 100),
        }));
        if (!totalProjSegments.length) {
            totalProjSegments.push({ color: "#2563eb", pct: 100 });
        }

        const healthSegments = [];
        if (goodCnt > 0) healthSegments.push({ color: "#10b981", pct: Math.round((goodCnt / Math.max(1, execTotal)) * 100) });
        if (fairCnt > 0) healthSegments.push({ color: "#f59e0b", pct: Math.round((fairCnt / Math.max(1, execTotal)) * 100) });
        if (poorCnt > 0) healthSegments.push({ color: "#ef4444", pct: Math.round((poorCnt / Math.max(1, execTotal)) * 100) });
        if (!healthSegments.length) healthSegments.push({ color: "#10b981", pct: 100 });

        const riskSegments = [];
        if (lowRiskCnt > 0) riskSegments.push({ color: "#10b981", pct: Math.round((lowRiskCnt / Math.max(1, execTotal)) * 100) });
        if (medRiskCnt > 0) riskSegments.push({ color: "#f59e0b", pct: Math.round((medRiskCnt / Math.max(1, execTotal)) * 100) });
        if (highRiskCnt > 0) riskSegments.push({ color: "#ef4444", pct: Math.round((highRiskCnt / Math.max(1, execTotal)) * 100) });
        if (!riskSegments.length) riskSegments.push({ color: "#10b981", pct: 100 });

        const totalTeamMembersCount = execProjects.reduce((sum, p) => sum + 1, 0);

        return {
            header: {
                brand_letter: companyName ? companyName[0].toUpperCase() : "B",
                title: this.state.departmentId ? `Project Dashboard · ${currentTitle}` : "Project Dashboard",
                subtitle: companyName,
                teams_legend: teamsLegend,
                date_str: todayStr,
            },
            top_kpis: {
                total_projects: {
                    count: execTotal,
                    sub: `${teamsCards.length} teams · ${totalTeamMembersCount} members`,
                    segments: totalProjSegments,
                },
                running_now: {
                    count: runningCnt,
                    total: execTotal,
                    sub: `${completedCnt} completed · ${onHoldCnt} on hold · ${notStartedCnt} not started`,
                    bar_pct: Math.round((runningCnt / Math.max(1, execTotal)) * 100),
                },
                overall_health: {
                    score: healthScore,
                    status: healthScore >= 75 ? "Good" : (healthScore >= 60 ? "Fair" : "Needs Focus"),
                    sub: `${goodCnt} good · ${fairCnt} fair · ${poorCnt} poor`,
                    segments: healthSegments,
                },
                high_risk: {
                    count: highRiskCnt,
                    sub_label: highRiskCnt > 0 ? "need action" : "under control",
                    sub: `${lowRiskCnt} low · ${medRiskCnt} medium · ${highRiskCnt} high`,
                    segments: riskSegments,
                },
                on_time: {
                    score: onTimeScore,
                    sub_label: "on time",
                    sub: `Average progress ${avgExecProg}% across projects`,
                    bar_pct: onTimeScore,
                },
            },
            project_health: {
                score: healthScore,
                good: goodCnt,
                fair: fairCnt,
                poor: poorCnt,
                donut_good: `${dGood} ${cLen}`,
                donut_fair: `${dFair} ${cLen}`,
                donut_poor: `${dPoor} ${cLen}`,
                donut_fair_offset: dFairOffset,
                donut_poor_offset: dPoorOffset,
            },
            running_status: {
                running: runningCnt,
                completed: completedCnt,
                on_hold: onHoldCnt,
                not_started: notStartedCnt,
                running_pct: Math.round((runningCnt / Math.max(1, execTotal)) * 100),
                completed_pct: Math.round((completedCnt / Math.max(1, execTotal)) * 100),
                on_hold_pct: Math.round((onHoldCnt / Math.max(1, execTotal)) * 100),
                not_started_pct: Math.round((notStartedCnt / Math.max(1, execTotal)) * 100),
            },
            risk_level: {
                label: riskLabelStr,
                needle_deg: needleDeg,
                low: lowRiskCnt,
                medium: medRiskCnt,
                high: highRiskCnt,
            },
            project_condition: {
                ahead: aheadCnt,
                on_plan: onPlanCnt,
                behind: behindCnt,
                overdue: overdueCnt,
                ahead_h: condHAhead,
                on_plan_h: condHOnPlan,
                behind_h: condHBehind,
                overdue_h: condHOverdue,
            },
            teams: teamsCards,
            team_comparison: {
                teams: teamCompNames,
                metrics: [
                    { name: "Productivity", color: "#0f172a", dark_color: "#f8fafc", values: teamCompProd },
                    { name: "Quality", color: "#2563eb", dark_color: "#3b82f6", values: teamCompQual },
                    { name: "On-time", color: "#93c5fd", dark_color: "#60a5fa", values: teamCompOntime },
                ],
            },
            projects: execProjects,
        };
    }

    get defaultExecutiveData() {
        const todayStr = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
        return {
            header: {
                brand_letter: "B",
                title: "Project Dashboard",
                subtitle: "Benac Business Solutions",
                teams_legend: [],
                date_str: todayStr,
            },
            top_kpis: {
                total_projects: {
                    count: 0,
                    sub: "0 teams · 0 consultants",
                    segments: [],
                },
                running_now: {
                    count: 0,
                    total: 0,
                    sub: "0 completed · 0 on hold · 0 not started",
                    bar_pct: 0,
                },
                overall_health: {
                    score: 100,
                    status: "Good",
                    sub: "0 good · 0 fair · 0 poor",
                    segments: [],
                },
                high_risk: {
                    count: 0,
                    sub_label: "under control",
                    sub: "0 low · 0 medium · 0 high",
                    segments: [],
                },
                on_time: {
                    score: 100,
                    sub_label: "on time",
                    sub: "Average progress 0% across projects",
                    bar_pct: 100,
                },
            },
            project_health: {
                score: 100,
                good: 0,
                fair: 0,
                poor: 0,
                donut_good: "301.6 301.6",
                donut_fair: "0.0 301.6",
                donut_poor: "0.0 301.6",
                donut_fair_offset: 0,
                donut_poor_offset: 0,
            },
            running_status: {
                running: 0,
                completed: 0,
                on_hold: 0,
                not_started: 0,
                running_pct: 0,
                completed_pct: 0,
                on_hold_pct: 0,
                not_started_pct: 0,
            },
            risk_level: {
                label: "Low risk portfolio",
                needle_deg: -60,
                low: 0,
                medium: 0,
                high: 0,
            },
            project_condition: {
                ahead: 0,
                on_plan: 0,
                behind: 0,
                overdue: 0,
                ahead_h: 0,
                on_plan_h: 0,
                behind_h: 0,
                overdue_h: 0,
            },
            teams: [],
            team_comparison: {
                teams: [],
                metrics: [
                    { name: "Productivity", color: "#0f172a", dark_color: "#f8fafc", values: [] },
                    { name: "Quality", color: "#2563eb", dark_color: "#3b82f6", values: [] },
                    { name: "On-time", color: "#93c5fd", dark_color: "#60a5fa", values: [] },
                ],
            },
            projects: [],
        };
    }

    get executiveProjects() {
        const data = this.executiveData;
        let list = (data && Array.isArray(data.projects)) ? data.projects : [];
        if (this.state.executiveFilterTeam !== "all") {
            const fKey = this.state.executiveFilterTeam;
            list = list.filter((p) => p.team === fKey || p.team_short === fKey || p.team_lead === fKey);
        }
        if (this.state.executiveFilterStatus !== "all") {
            list = list.filter((p) => p.status === this.state.executiveFilterStatus);
        }
        if (this.state.executiveFilterHealth !== "all") {
            list = list.filter((p) => p.health === this.state.executiveFilterHealth);
        }
        if (this.state.executiveSearch) {
            const q = this.state.executiveSearch.toLowerCase();
            list = list.filter(
                (p) =>
                    (p.name && p.name.toLowerCase().includes(q)) ||
                    (p.client && p.client.toLowerCase().includes(q)) ||
                    (p.team && p.team.toLowerCase().includes(q))
            );
        }
        return list;
    }

    filterExecutiveTeam(teamName) {
        this.state.executiveFilterTeam = this.state.executiveFilterTeam === teamName ? "all" : teamName;
    }

    filterExecutiveStatus(status) {
        this.state.executiveFilterStatus = this.state.executiveFilterStatus === status ? "all" : status;
    }

    filterExecutiveHealth(health) {
        this.state.executiveFilterHealth = this.state.executiveFilterHealth === health ? "all" : health;
    }

    onExecutiveSearch(ev) {
        this.state.executiveSearch = (ev.target.value || "").trim();
    }

    // SAFE GETTERS FOR TEMPLATE
    get kpis() {
        if (!this.state.data || !this.state.data.kpis) {
            return {
                active_projects: 0,
                completed_projects: 0,
                avg_progress: 0,
                needs_attention: 0,
                delayed_count: 0,
                budget_used_pct: 0,
                budget_spent_str: "$0K",
                budget_total_str: "$0K",
                total_kras: 0,
                active_kras: 0,
                avg_kra_performance: 0,
                total_kpis: 0,
            };
        }
        return this.state.data.kpis;
    }

    get departments() {
        return (this.state.data && this.state.data.departments) || [];
    }

    get stagesData() {
        return (this.state.data && this.state.data.stages) || [];
    }

    get phasesData() {
        return (this.state.data && this.state.data.phases) || [];
    }

    get sopsData() {
        if (!this.state.data || !this.state.data.sops) {
            return { total: 0, active: 0, draft: 0, audit: 0, records: [] };
        }
        return this.state.data.sops;
    }

    get sopsRecords() {
        if (!this.state.data || !this.state.data.sops || !Array.isArray(this.state.data.sops.records)) {
            return [];
        }
        return this.state.data.sops.records;
    }

    get approvalsData() {
        if (!this.state.data || !this.state.data.approvals) {
            return { total: 0, pending: 0, approved: 0, rejected: 0, records: [] };
        }
        return this.state.data.approvals;
    }

    get approvalsRecords() {
        if (!this.state.data || !this.state.data.approvals || !Array.isArray(this.state.data.approvals.records)) {
            return [];
        }
        return this.state.data.approvals.records;
    }

    get dueNext() {
        return (this.state.data && this.state.data.due_next) || [];
    }

    get companyName() {
        return (this.state.data && this.state.data.company_name) || "Northwind Co.";
    }

    get currentTitle() {
        return (this.state.data && this.state.data.current_title) || "All departments";
    }

    get totalAllProjects() {
        if (!this.state.data) return 0;
        return this.state.data.total_all_projects || 0;
    }

    get totalShownProjects() {
        if (!this.state.data) return 0;
        return this.state.data.total_shown_projects || 0;
    }

    // LOAD DATA
    async loadDashboardData() {
        try {
            this.state.loading = true;
            this.state.error = false;

            const data = await this.orm.call(
                "benjali.management.dashboard",
                "get_dashboard_data",
                [this.state.departmentId]
            );

            // Backward compatibility fallback in case server response is legacy
            if (data) {
                if (!data.kpis) {
                    const p = data.projects && typeof data.projects === "object" && !Array.isArray(data.projects)
                        ? data.projects
                        : {};
                    data.kpis = {
                        active_projects: p.active || p.total || 0,
                        completed_projects: p.completed || 0,
                        avg_progress: 50,
                        needs_attention: (p.on_hold || 0) + (p.cancelled || 0),
                        delayed_count: p.on_hold || 0,
                        budget_used_pct: 71,
                        budget_spent_str: "$1,070K",
                        budget_total_str: "$1,500K",
                        total_kras: 0,
                        active_kras: 0,
                        avg_kra_performance: 0,
                        total_kpis: 0,
                    };
                }
                data.departments = Array.isArray(data.departments) ? data.departments : [];
                data.projects = Array.isArray(data.projects) ? data.projects : [];
                for (const proj of data.projects) {
                    proj.project_manager = proj.project_manager || { name: proj.owner || 'Unassigned', email: '', initials: 'PM', is_assigned: false };
                    proj.project_responsible = proj.project_responsible || { name: 'Unassigned', email: '', initials: 'PR', is_assigned: false };
                    proj.employee_performance = Array.isArray(proj.employee_performance) ? proj.employee_performance : [];
                    proj.team_members = Array.isArray(proj.team_members) ? proj.team_members : [];
                    proj.tasks = Array.isArray(proj.tasks) ? proj.tasks : [];
                    proj.activities = Array.isArray(proj.activities) ? proj.activities : [];
                    proj.team_count = proj.team_count || proj.team_members.length;
                    proj.task_count = proj.task_count || proj.tasks.length;
                    proj.activity_count = proj.activity_count || proj.activities.length;
                    proj.kras = Array.isArray(proj.kras) ? proj.kras : [];
                    for (const kra of proj.kras) {
                        kra.kpis = Array.isArray(kra.kpis) ? kra.kpis : [];
                        kra.employees = Array.isArray(kra.employees) ? kra.employees : [];
                    }
                }
                if (!this.state.selectedPerformanceProjectId && data.projects.length > 0) {
                    this.state.selectedPerformanceProjectId = data.projects[0].id;
                }
                data.due_next = Array.isArray(data.due_next) ? data.due_next : [];
                data.stages = Array.isArray(data.stages) ? data.stages : [];
                data.phases = Array.isArray(data.phases) ? data.phases : [];
                data.sops = data.sops || { total: 0, active: 0, draft: 0, audit: 0, records: [] };
                data.sops.records = Array.isArray(data.sops.records) ? data.sops.records : [];
                data.approvals = data.approvals || { total: 0, pending: 0, approved: 0, rejected: 0, records: [] };
                data.approvals.records = Array.isArray(data.approvals.records) ? data.approvals.records : [];
                data.all_kras = Array.isArray(data.all_kras) ? data.all_kras : [];
                data.all_kpis = Array.isArray(data.all_kpis) ? data.all_kpis : [];
                if (!data.total_all_projects) data.total_all_projects = data.kpis.active_projects + data.kpis.completed_projects;
                if (!data.total_shown_projects) data.total_shown_projects = data.projects.length || data.total_all_projects;
                if (!data.current_title) data.current_title = "All departments";
                if (!data.company_name) data.company_name = "Northwind Co.";

                // Safe fallback for chart_data if backend hasn't restarted yet
                if (!data.chart_data) {
                    data.chart_data = {
                        by_department: (data.departments || []).map((d) => ({
                            id: d.id,
                            label: d.name,
                            value: d.count || 0,
                            color: d.color || "#a855f7",
                        })),
                        by_status: [
                            { id: "on_track", label: "On Track", value: (data.projects || []).filter((p) => p.status === "on_track").length, color: "#10b981" },
                            { id: "at_risk", label: "At Risk", value: (data.projects || []).filter((p) => p.status === "at_risk").length, color: "#f59e0b" },
                            { id: "delayed", label: "Delayed", value: (data.projects || []).filter((p) => p.status === "delayed").length, color: "#ef4444" },
                            { id: "done", label: "Done", value: (data.projects || []).filter((p) => p.status === "done").length, color: "#3b82f6" },
                        ],
                        monthly_trend: [
                            { id: "m1", label: "May", value: Math.max(1, Math.floor(data.projects.length * 0.4)), color: "#3b82f6" },
                            { id: "m2", label: "Jun", value: Math.max(2, Math.floor(data.projects.length * 0.55)), color: "#3b82f6" },
                            { id: "m3", label: "Jul", value: Math.max(2, Math.floor(data.projects.length * 0.7)), color: "#3b82f6" },
                            { id: "m4", label: "Aug", value: Math.max(3, Math.floor(data.projects.length * 0.8)), color: "#3b82f6" },
                            { id: "m5", label: "Sep", value: Math.max(4, Math.floor(data.projects.length * 0.9)), color: "#3b82f6" },
                            { id: "m6", label: "Oct", value: data.projects.length, color: "#3b82f6" },
                        ],
                    };
                }
            }

            this.state.data = data;
        } catch (error) {
            console.error("Dashboard error:", error);
            this.state.error = true;
        } finally {
            this.state.loading = false;
        }
    }

    // DEPARTMENT SELECTOR
    async selectDepartment(departmentId) {
        this.state.departmentId = departmentId ? parseInt(departmentId, 10) : false;
        this.state.statusFilter = "all";
        this.state.searchQuery = "";
        await this.loadDashboardData();
    }

    // STATUS FILTER TABS
    setStatusFilter(filter) {
        this.state.statusFilter = filter;
    }

    // SEARCH FILTER
    onSearchInput(event) {
        this.state.searchQuery = (event.target.value || "").toLowerCase().trim();
    }

    // EXPAND/COLLAPSE PROJECT KRA SECTION
    toggleProjectKra(projectId) {
        this.state.expandedProjects[projectId] = !this.state.expandedProjects[projectId];
    }

    // EXPAND/COLLAPSE INLINE PROJECT DETAILS (MANAGER, TEAM, TASKS, ACTIVITIES)
    toggleProjectDetails(projectId) {
        this.state.expandedProjectDetails[projectId] = !this.state.expandedProjectDetails[projectId];
    }

    // OPEN DETAILED SLIDE-OVER MODAL FOR PROJECT
    openProjectModal(project) {
        this.state.selectedProjectDetail = project;
    }

    closeProjectModal() {
        this.state.selectedProjectDetail = null;
    }

    // FILTERED PROJECTS GETTER
    get filteredProjects() {
        if (!this.state.data) return [];
        let list = Array.isArray(this.state.data.projects) ? this.state.data.projects : [];
        if (!list.length) return [];

        if (this.state.statusFilter !== "all") {
            list = list.filter((p) => p.status === this.state.statusFilter);
        }

        if (this.state.projectPriorityFilter !== "all") {
            list = list.filter((p) => String(p.priority || "0") === this.state.projectPriorityFilter);
        }

        if (this.state.searchQuery) {
            const query = this.state.searchQuery;
            list = list.filter(
                (p) =>
                    (p.name && p.name.toLowerCase().includes(query)) ||
                    (p.owner && p.owner.toLowerCase().includes(query)) ||
                    (p.department_name && p.department_name.toLowerCase().includes(query)) ||
                    (p.project_manager && p.project_manager.name && p.project_manager.name.toLowerCase().includes(query))
            );
        }

        for (const proj of list) {
            proj.project_manager = proj.project_manager || { name: proj.owner || 'Unassigned', email: '', initials: 'PM', is_assigned: false };
            proj.team_members = Array.isArray(proj.team_members) ? proj.team_members : [];
            proj.tasks = Array.isArray(proj.tasks) ? proj.tasks : [];
            proj.activities = Array.isArray(proj.activities) ? proj.activities : [];
            proj.team_count = proj.team_count || proj.team_members.length;
            proj.task_count = proj.task_count || proj.tasks.length;
            proj.activity_count = proj.activity_count || proj.activities.length;
            if (!Array.isArray(proj.kras)) {
                proj.kras = [];
            }
            for (const kra of proj.kras) {
                if (!Array.isArray(kra.kpis)) {
                    kra.kpis = [];
                }
            }
        }

        return list;
    }

    // EMPLOYEE PERFORMANCE GETTERS & METHODS
    selectPerformanceProject(projectId) {
        this.state.selectedPerformanceProjectId = Number(projectId);
    }

    setPerformanceRoleFilter(role) {
        this.state.performanceRoleFilter = role;
    }

    onPerformanceSearch(event) {
        this.state.performanceSearchQuery = (event.target.value || "").toLowerCase().trim();
    }

    toggleEmpCard(empId) {
        this.state.expandedEmpCards[empId] = !this.state.expandedEmpCards[empId];
    }

    openProjectPerformance(projectId) {
        this.state.selectedPerformanceProjectId = Number(projectId);
        this.state.activeTab = "performance";
    }

    async openUser(userId) {
        if (!userId) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Employee Profile",
            res_model: "res.users",
            res_id: userId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    get currentPerformanceProject() {
        const projects = this.filteredProjects;
        if (!projects || !projects.length) return null;
        if (this.state.selectedPerformanceProjectId) {
            const found = projects.find((p) => p.id === this.state.selectedPerformanceProjectId);
            if (found) return found;
        }
        return projects[0];
    }

    get currentProjectEmployees() {
        const project = this.currentPerformanceProject;
        if (!project || !Array.isArray(project.employee_performance)) return [];
        let list = project.employee_performance;

        if (this.state.performanceSearchQuery) {
            const query = this.state.performanceSearchQuery;
            list = list.filter(
                (emp) =>
                    (emp.name && emp.name.toLowerCase().includes(query)) ||
                    (emp.email && emp.email.toLowerCase().includes(query)) ||
                    (emp.roles && emp.roles.some((r) => r.toLowerCase().includes(query)))
            );
        }

        const rf = this.state.performanceRoleFilter;
        if (rf === "pm") {
            list = list.filter((e) => e.is_pm);
        } else if (rf === "pr") {
            list = list.filter((e) => e.is_responsible);
        } else if (rf === "kra") {
            list = list.filter((e) => (e.roles && e.roles.some((r) => r.includes("KRA") || r.includes("Scope"))) || (e.kras && e.kras.length > 0));
        } else if (rf === "kpi") {
            list = list.filter((e) => (e.roles && e.roles.some((r) => r.includes("KPI") || r.includes("Task"))) || e.kpi_count > 0);
        }

        return list;
    }

    get currentProjectKras() {
        const project = this.currentPerformanceProject;
        if (!project || !Array.isArray(project.kras)) return [];
        let list = project.kras;
        if (this.state.performanceSearchQuery) {
            const query = this.state.performanceSearchQuery;
            list = list.filter(
                (k) =>
                    (k.name && k.name.toLowerCase().includes(query)) ||
                    (k.code && k.code.toLowerCase().includes(query)) ||
                    (k.lead && k.lead.toLowerCase().includes(query)) ||
                    (k.employees && k.employees.some((e) => e.name && e.name.toLowerCase().includes(query)))
            );
        }
        return list;
    }

    get kraPerformanceSummary() {
        const kras = (this.currentPerformanceProject && this.currentPerformanceProject.kras) || [];
        const total = kras.length;
        const completed = kras.filter((k) => k.state === "completed").length;
        const ongoing = kras.filter((k) => k.state !== "completed" && k.state !== "cancelled").length;
        const avgProg = total > 0 ? Math.round(kras.reduce((acc, k) => acc + (Number(k.weekly_progress) || 0), 0) / total) : 0;
        return { total, completed, ongoing, avgProg };
    }

    get kpiPerformanceSummary() {
        const p = this.currentPerformanceProject;
        if (!p) return { total: 0, completed: 0, pending: 0, avgProg: 0, assigneeCount: 0 };
        const employees = (p.employee_performance || []).filter((e) => (e.roles && e.roles.some((r) => r.includes("KPI"))) || e.kpi_count > 0);
        const total = p.kpi_count || 0;
        const completed = (p.workflow_hierarchy && p.workflow_hierarchy.team_kpis_completed) || 0;
        const pending = Math.max(0, total - completed);
        const avgProg = (p.workflow_hierarchy && p.workflow_hierarchy.team_avg_progress) || p.progress || 0;
        return { total, completed, pending, avgProg, assigneeCount: employees.length };
    }

    get currentPmEmployee() {
        const p = this.currentPerformanceProject;
        if (!p || !Array.isArray(p.employee_performance)) return null;
        return p.employee_performance.find((e) => e.is_pm) || null;
    }

    get currentPrEmployee() {
        const p = this.currentPerformanceProject;
        if (!p || !Array.isArray(p.employee_performance)) return null;
        return p.employee_performance.find((e) => e.is_responsible) || null;
    }

    // OPEN PROJECT FORM VIEW
    async openProject(projectId) {
        if (!projectId) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Business Project",
            res_model: "business.project",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // OPEN STAGE PROJECTS
    async openStageProjects(stageId, stageName = "Stage Projects") {
        const domain = [["stage_id", "=", stageId]];
        if (this.state.departmentId) {
            domain.push(["department_id", "=", this.state.departmentId]);
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: stageName,
            res_model: "business.project",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    // OPEN PHASE PROJECTS
    async openPhaseProjects(phaseCode, phaseName = "Phase Projects") {
        const domain = [["phase", "=", phaseCode]];
        if (this.state.departmentId) {
            domain.push(["department_id", "=", this.state.departmentId]);
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: phaseName,
            res_model: "business.project",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    // APPROVALS MANAGEMENT
    async createApproval() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "New Approval Request",
            res_model: "business.project.approval",
            views: [[false, "form"]],
            target: "new",
        });
        await this.loadDashboardData();
    }

    async approveRequest(approvalId) {
        try {
            await this.orm.call("business.project.approval", "action_approve", [[approvalId]]);
            this.notification.add("Approval request approved successfully.", { type: "success" });
            await this.loadDashboardData();
        } catch (error) {
            this.notification.add(error.message || "Approval action failed.", { type: "danger" });
        }
    }

    async rejectRequest(approvalId) {
        try {
            await this.orm.call("business.project.approval", "action_reject", [[approvalId]]);
            this.notification.add("Approval request rejected.", { type: "warning" });
            await this.loadDashboardData();
        } catch (error) {
            this.notification.add(error.message || "Rejection action failed.", { type: "danger" });
        }
    }

    async openApproval(approvalId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Approval Request",
            res_model: "business.project.approval",
            res_id: approvalId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // SOPS MANAGEMENT
    async createSop() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "New SOP / Checklist",
            res_model: "business.project.sop",
            views: [[false, "form"]],
            target: "new",
        });
        await this.loadDashboardData();
    }

    async openSop(sopId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Standard Operating Procedure",
            res_model: "business.project.sop",
            res_id: sopId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // OPEN ALL PROJECTS LIST
    async openProjectsList(status = null) {
        const domain = [];
        if (this.state.departmentId) {
            domain.push(["department_id", "=", this.state.departmentId]);
        }
        if (status === "active") {
            domain.push(["active", "=", true]);
            domain.push(["stage_id.name", "!=", "Completed"]);
        } else if (status === "completed") {
            domain.push(["stage_id.name", "=", "Completed"]);
        } else if (status === "attention") {
            domain.push(["stage_id.name", "in", ["On Hold", "Cancelled"]]);
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Business Projects",
            res_model: "business.project",
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "form"],
            ],
            domain: domain,
            context: {
                default_department_id: this.state.departmentId || false,
            },
        });
    }

    // KRA & KPI GETTERS
    get allKras() {
        if (!this.state.data) return [];
        let list = Array.isArray(this.state.data.all_kras) ? this.state.data.all_kras : [];
        if (this.state.kraStageFilter !== "all") {
            list = list.filter((k) => k.state === this.state.kraStageFilter);
        }
        if (this.state.kraPriorityFilter !== "all") {
            list = list.filter((k) => String(k.priority || "0") === this.state.kraPriorityFilter);
        }
        if (this.state.searchQuery) {
            const q = this.state.searchQuery;
            list = list.filter(
                (k) =>
                    (k.name && k.name.toLowerCase().includes(q)) ||
                    (k.code && k.code.toLowerCase().includes(q)) ||
                    (k.project_name && k.project_name.toLowerCase().includes(q)) ||
                    (k.lead && k.lead.toLowerCase().includes(q))
            );
        }
        return list;
    }

    get allKpis() {
        if (!this.state.data) return [];
        let list = Array.isArray(this.state.data.all_kpis) ? this.state.data.all_kpis : [];
        if (this.state.kpiStageFilter !== "all") {
            list = list.filter((k) => k.state === this.state.kpiStageFilter);
        }
        if (this.state.kpiPriorityFilter !== "all") {
            list = list.filter((k) => String(k.priority || "0") === this.state.kpiPriorityFilter);
        }
        if (this.state.searchQuery) {
            const q = this.state.searchQuery;
            list = list.filter(
                (k) =>
                    (k.name && k.name.toLowerCase().includes(q)) ||
                    (k.code && k.code.toLowerCase().includes(q)) ||
                    (k.project_name && k.project_name.toLowerCase().includes(q)) ||
                    (k.kra_name && k.kra_name.toLowerCase().includes(q)) ||
                    (k.employee && k.employee.toLowerCase().includes(q))
            );
        }
        return list;
    }

    // SUB-VIEW & FILTER NAVIGATION
    setKpiViewMode(mode) {
        this.state.kpiViewMode = mode;
    }

    setKraStageFilter(filter) {
        this.state.kraStageFilter = filter;
    }

    setKpiStageFilter(filter) {
        this.state.kpiStageFilter = filter;
    }

    setProjectPriorityFilter(filter) {
        this.state.projectPriorityFilter = filter;
    }

    setKraPriorityFilter(filter) {
        this.state.kraPriorityFilter = filter;
    }

    setKpiPriorityFilter(filter) {
        this.state.kpiPriorityFilter = filter;
    }

    get kraPriorityCounts() {
        const counts = { all: 0, "3": 0, "2": 0, "1": 0, "0": 0 };
        if (!this.state.data || !Array.isArray(this.state.data.all_kras)) return counts;
        const all = this.state.data.all_kras;
        counts.all = all.length;
        for (const k of all) {
            const prio = String(k.priority || "0");
            if (counts[prio] !== undefined) {
                counts[prio]++;
            } else {
                counts["0"]++;
            }
        }
        return counts;
    }

    get kpiPriorityCounts() {
        const counts = { all: 0, "3": 0, "2": 0, "1": 0, "0": 0 };
        if (!this.state.data || !Array.isArray(this.state.data.all_kpis)) return counts;
        const all = this.state.data.all_kpis;
        counts.all = all.length;
        for (const k of all) {
            const prio = String(k.priority || "0");
            if (counts[prio] !== undefined) {
                counts[prio]++;
            } else {
                counts["0"]++;
            }
        }
        return counts;
    }

    async setKraPriority(kraId, priority) {
        try {
            await this.orm.call("benjali.management.dashboard", "set_kra_priority", [kraId, String(priority)]);
            if (this.state.data && Array.isArray(this.state.data.all_kras)) {
                const k = this.state.data.all_kras.find((item) => item.id === kraId);
                if (k) {
                    k.priority = String(priority);
                }
            }
            this.notification.add("Scope priority updated.", { type: "success" });
            await this.loadDashboardData();
        } catch (error) {
            this.notification.add(error.message || "Failed to update Scope priority.", { type: "danger" });
        }
    }

    async setKpiPriority(kpiId, priority) {
        try {
            await this.orm.call("benjali.management.dashboard", "set_kpi_priority", [kpiId, String(priority)]);
            if (this.state.data && Array.isArray(this.state.data.all_kpis)) {
                const k = this.state.data.all_kpis.find((item) => item.id === kpiId);
                if (k) {
                    k.priority = String(priority);
                }
            }
            this.notification.add("Task priority updated.", { type: "success" });
            await this.loadDashboardData();
        } catch (error) {
            this.notification.add(error.message || "Failed to update Task priority.", { type: "danger" });
        }
    }

    get projectPriorityCounts() {
        const counts = { all: 0, "3": 0, "2": 0, "1": 0, "0": 0 };
        if (!this.state.data || !Array.isArray(this.state.data.projects)) return counts;
        const allProj = this.state.data.projects;
        counts.all = allProj.length;
        for (const p of allProj) {
            const prio = String(p.priority || "0");
            if (counts[prio] !== undefined) {
                counts[prio]++;
            } else {
                counts["0"]++;
            }
        }
        return counts;
    }

    async setProjectPriority(projectId, priority) {
        try {
            await this.orm.call("benjali.management.dashboard", "set_project_priority", [projectId, String(priority)]);
            if (this.state.data && Array.isArray(this.state.data.projects)) {
                const proj = this.state.data.projects.find((p) => p.id === projectId);
                if (proj) {
                    proj.priority = String(priority);
                }
            }
            this.notification.add("Project priority updated.", { type: "success" });
            await this.loadDashboardData();
        } catch (error) {
            this.notification.add(error.message || "Failed to update project priority.", { type: "danger" });
        }
    }

    toggleKra(kraId) {
        this.state.expandedKras[kraId] = !this.state.expandedKras[kraId];
    }

    // SCOPE ACTIONS & MANAGEMENT
    async createKra(projectId = false) {
        const context = {};
        if (projectId) {
            context.default_project_id = projectId;
        } else if (this.state.departmentId) {
            context.default_department_id = this.state.departmentId;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Create Scope",
            res_model: "business.project.kra",
            views: [[false, "form"]],
            target: "new",
            context: context,
        });
        await this.loadDashboardData();
    }

    async openKra(kraId) {
        if (!kraId) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Scope",
            res_model: "business.project.kra",
            res_id: kraId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openKraKanban() {
        const domain = [];
        if (this.state.departmentId) {
            domain.push(["department_id", "=", this.state.departmentId]);
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Scope Stages Kanban",
            res_model: "business.project.kra",
            views: [
                [false, "kanban"],
                [false, "list"],
                [false, "form"],
            ],
            domain: domain,
            context: { search_default_group_stage_id: 1 },
        });
    }

    async setKraStage(kraId, state) {
        try {
            await this.orm.call("benjali.management.dashboard", "set_kra_stage", [kraId, state]);
            this.notification.add("Scope stage updated successfully.", { type: "success" });
            await this.loadDashboardData();
        } catch (error) {
            this.notification.add(error.message || "Failed to update Scope stage.", { type: "danger" });
        }
    }

    // TASK ACTIONS & MANAGEMENT
    async createKpi(kraId = false, projectId = false) {
        const context = {};
        if (kraId) context.default_kra_id = kraId;
        if (projectId) context.default_project_id = projectId;
        if (this.state.departmentId) context.default_department_id = this.state.departmentId;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Create Task",
            res_model: "business.project.kpi",
            views: [[false, "form"]],
            target: "new",
            context: context,
        });
        await this.loadDashboardData();
    }

    async openKpi(kpiId) {
        if (!kpiId) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Task",
            res_model: "business.project.kpi",
            res_id: kpiId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openKpiKanban() {
        const domain = [];
        if (this.state.departmentId) {
            domain.push(["department_id", "=", this.state.departmentId]);
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Task Stages Kanban",
            res_model: "business.project.kpi",
            views: [
                [false, "kanban"],
                [false, "list"],
                [false, "form"],
            ],
            domain: domain,
            context: { search_default_group_stage_id: 1 },
        });
    }

    async setKpiStage(kpiId, state) {
        try {
            await this.orm.call("benjali.management.dashboard", "set_kpi_stage", [kpiId, state]);
            this.notification.add("Task stage updated successfully.", { type: "success" });
            await this.loadDashboardData();
        } catch (error) {
            this.notification.add(error.message || "Failed to update Task stage.", { type: "danger" });
        }
    }

    async updateKpiProgress(kpiId, eventOrVal) {
        let val;
        if (typeof eventOrVal === "number") {
            val = eventOrVal;
        } else if (eventOrVal && eventOrVal.target) {
            val = parseFloat(eventOrVal.target.value || 0);
        } else {
            val = 0;
        }
        const clamped = Math.min(100, Math.max(0, val));
        try {
            await this.orm.call("benjali.management.dashboard", "update_kpi_progress", [kpiId, clamped]);
            this.notification.add(`Task progress updated to ${clamped}%.`, { type: "success" });
            await this.loadDashboardData();
        } catch (error) {
            this.notification.add(error.message || "Failed to update Task progress.", { type: "danger" });
        }
    }

    async logKpiTimesheet(kpiId, projectId = false) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Log Task Timesheet",
            res_model: "account.analytic.line",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_kpi_id: kpiId,
                default_project_id: projectId || false,
            },
        });
        await this.loadDashboardData();
    }

    async viewKpiTimesheets(kpiId, kpiName = "Task") {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: `Timesheets - ${kpiName}`,
            res_model: "account.analytic.line",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [["kpi_id", "=", kpiId]],
        });
    }

    // ================= CALENDAR & TASK SCHEDULING GETTERS & METHODS =================
    get calendarData() {
        return (this.state.data && this.state.data.calendar) || {};
    }

    get calendarMonthLabel() {
        const year = this.state.calendarYear;
        const month = this.state.calendarMonth;
        const date = new Date(year, month, 1);
        return date.toLocaleString("default", { month: "long", year: "numeric" });
    }

    get calendarDays() {
        const year = this.state.calendarYear;
        const month = this.state.calendarMonth;
        const firstDayOfMonth = new Date(year, month, 1);
        let startDayOfWeek = firstDayOfMonth.getDay() - 1; // 0=Mon, 6=Sun
        if (startDayOfWeek === -1) startDayOfWeek = 6;

        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const daysInPrevMonth = new Date(year, month, 0).getDate();

        const allEvents = (this.calendarData && this.calendarData.events) || [];
        const todayStr = this.calendarData.today_str || "";

        const days = [];

        // Previous month padding days
        for (let i = startDayOfWeek - 1; i >= 0; i--) {
            const d = daysInPrevMonth - i;
            const prevM = month === 0 ? 11 : month - 1;
            const prevY = month === 0 ? year - 1 : year;
            const dateStr = `${prevY}-${String(prevM + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
            days.push(this._buildDayCell(dateStr, d, false, dateStr === todayStr, allEvents));
        }

        // Current month days
        for (let d = 1; d <= daysInMonth; d++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
            days.push(this._buildDayCell(dateStr, d, true, dateStr === todayStr, allEvents));
        }

        // Next month padding days to reach multiple of 7
        const totalCells = days.length <= 35 ? 35 : 42;
        let nextD = 1;
        while (days.length < totalCells) {
            const nextM = month === 11 ? 0 : month + 1;
            const nextY = month === 11 ? year + 1 : year;
            const dateStr = `${nextY}-${String(nextM + 1).padStart(2, "0")}-${String(nextD).padStart(2, "0")}`;
            days.push(this._buildDayCell(dateStr, nextD, false, dateStr === todayStr, allEvents));
            nextD++;
        }

        return days;
    }

    _buildDayCell(dateStr, dayNum, isCurrentMonth, isToday, allEvents) {
        let events = allEvents.filter((e) => e.date === dateStr);
        const filter = this.state.calendarFilter;
        if (filter === "pending") {
            events = events.filter((e) => e.state !== "completed" && e.state !== "cancelled");
        } else if (filter === "kra") {
            events = events.filter((e) => e.type === "kra");
        } else if (filter === "kpi") {
            events = events.filter((e) => e.type === "kpi");
        } else if (filter === "today") {
            events = events.filter((e) => e.is_today);
        } else if (filter === "tomorrow") {
            events = events.filter((e) => e.is_tomorrow);
        } else if (filter === "overdue") {
            events = events.filter((e) => e.is_overdue);
        }

        const isSelected = this.state.selectedCalendarDate === dateStr;
        const hasOverdue = events.some((e) => e.is_overdue);
        const hasPending = events.some((e) => e.state !== "completed" && e.state !== "cancelled");

        return {
            dateStr,
            dayNum,
            isCurrentMonth,
            isToday,
            isSelected,
            hasOverdue,
            hasPending,
            events,
            eventCount: events.length,
        };
    }

    get selectedDateEvents() {
        if (!this.state.selectedCalendarDate) return [];
        const allEvents = (this.calendarData && this.calendarData.events) || [];
        return allEvents.filter((e) => e.date === this.state.selectedCalendarDate);
    }

    get currentAgendaTasks() {
        const cal = this.calendarData;
        const tab = this.state.calendarAgendaTab || "today_pending";
        if (tab === "today_pending") {
            return cal.today_pending_tasks || [];
        } else if (tab === "tomorrow") {
            return cal.tomorrow_tasks || [];
        } else if (tab === "overdue") {
            return cal.overdue_tasks || [];
        } else if (tab === "today_completed") {
            return cal.today_completed_tasks || [];
        } else if (tab === "selected") {
            return this.selectedDateEvents;
        }
        return cal.today_pending_tasks || [];
    }

    prevMonth() {
        if (this.state.calendarMonth === 0) {
            this.state.calendarMonth = 11;
            this.state.calendarYear -= 1;
        } else {
            this.state.calendarMonth -= 1;
        }
    }

    nextMonth() {
        if (this.state.calendarMonth === 11) {
            this.state.calendarMonth = 0;
            this.state.calendarYear += 1;
        } else {
            this.state.calendarMonth += 1;
        }
    }

    todayMonth() {
        const now = new Date();
        this.state.calendarYear = now.getFullYear();
        this.state.calendarMonth = now.getMonth();
        const todayStr = this.calendarData.today_str || `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
        this.selectCalendarDate(todayStr);
    }

    setCalendarFilter(filter) {
        this.state.calendarFilter = filter;
    }

    setCalendarAgendaTab(tab) {
        this.state.calendarAgendaTab = tab;
    }

    selectCalendarDate(dateStr) {
        this.state.selectedCalendarDate = dateStr;
        this.state.calendarAgendaTab = "selected";
    }

    async openCalendarEvent(item) {
        if (!item) return;
        if (item.type === "kpi") {
            await this.openKpi(item.id);
        } else {
            await this.openKra(item.id);
        }
    }

    async openCalendarTaskList(filterType) {
        this.setCalendarAgendaTab(filterType);
        let actionName = "Deliverables";
        const domain = [];

        if (this.state.departmentId) {
            domain.push(["department_id", "=", this.state.departmentId]);
        }

        if (filterType === "today_pending") {
            actionName = "Today's Pending Tasks";
            domain.push(["is_today", "=", true]);
            domain.push(["state", "not in", ["completed", "cancelled"]]);
        } else if (filterType === "tomorrow") {
            actionName = "Tomorrow's Tasks";
            domain.push(["is_tomorrow", "=", true]);
            domain.push(["state", "not in", ["completed", "cancelled"]]);
        } else if (filterType === "overdue") {
            actionName = "Overdue Tasks";
            domain.push(["is_overdue", "=", true]);
        } else if (filterType === "today_completed") {
            actionName = "Completed Today";
            domain.push(["is_today", "=", true]);
            domain.push(["state", "=", "completed"]);
        } else if (filterType === "selected" && this.state.selectedCalendarDate) {
            actionName = `Tasks for ${this.state.selectedCalendarDate}`;
            domain.push(["date", "=", this.state.selectedCalendarDate]);
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: actionName,
            res_model: "business.project.kpi",
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "calendar"],
                [false, "form"],
            ],
            domain: domain,
            context: {
                default_department_id: this.state.departmentId || false,
                search_default_group_stage_id: 1,
            },
            target: "current",
        });
    }

    async openOdooCalendar(modelType) {
        const isKpi = modelType === "kpi";
        const model = isKpi ? "business.project.kpi" : "business.project.kra";
        const actionName = isKpi ? "Task Calendar View" : "Scope Calendar View";
        const domain = [];
        if (this.state.departmentId) {
            domain.push(["department_id", "=", this.state.departmentId]);
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: actionName,
            res_model: model,
            views: [
                [false, "calendar"],
                [false, "kanban"],
                [false, "list"],
                [false, "form"],
            ],
            domain: domain,
            target: "current",
        });
    }

    // EXPORT ACTION
    exportDashboard() {
        window.print();
    }
}

registry.category("actions").add("benjali_management_dashboard", BenjaliDashboard);

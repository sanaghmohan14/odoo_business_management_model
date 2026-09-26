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

        this.state = useState({
            loading: true,
            error: false,
            data: null,

            // false means All Departments
            departmentId: false,
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }


    // =========================================================
    // LOAD DASHBOARD
    // =========================================================

    async loadDashboardData() {

        try {

            this.state.loading = true;
            this.state.error = false;

            const departmentId =
                this.state.departmentId || false;

            console.log(
                "Loading dashboard for department:",
                departmentId
            );

            const data = await this.orm.call(
                "benjali.management.dashboard",
                "get_dashboard_data",
                [departmentId]
            );

            console.log(
                "Dashboard data received:",
                data
            );

            this.state.data = data;

        } catch (error) {

            console.error(
                "Benjali Dashboard Error:",
                error
            );

            this.state.error = true;

        } finally {

            this.state.loading = false;
        }
    }


    // =========================================================
    // DEPARTMENT CHANGE
    // =========================================================

    async onDepartmentChange(event) {

        const selectedValue = event.target.value;

        if (!selectedValue) {

            this.state.departmentId = false;

        } else {

            this.state.departmentId =
                parseInt(selectedValue, 10);
        }

        console.log(
            "Selected Department ID:",
            this.state.departmentId
        );

        // Clear old dashboard data first
        // so old values are not displayed
        // while the new values are loading.
        this.state.data = null;

        await this.loadDashboardData();
    }


    // =========================================================
    // STATUS DONUT
    // =========================================================

    getStatusChartStyle() {

        if (!this.state.data) {
            return "";
        }

        const data = this.state.data.status;

        const total = data.reduce(
            (sum, item) => sum + item.count,
            0
        );

        if (!total) {
            return "background: #e9ecef;";
        }

        const colors = [
            "#3b82f6",
            "#8b5cf6",
            "#f59e0b",
            "#ef4444",
        ];

        let current = 0;

        const parts = [];

        data.forEach((item, index) => {

            const percentage =
                (item.count / total) * 100;

            const start = current;
            const end = current + percentage;

            parts.push(
                `${colors[index]} ${start}% ${end}%`
            );

            current = end;
        });

        return `background: conic-gradient(${parts.join(", ")});`;
    }


    // =========================================================
    // ACTIVITY DONUT
    // =========================================================

    getActivityChartStyle() {

        if (!this.state.data) {
            return "";
        }

        return this.createDonutStyle(
            this.state.data.activities.chart,
            [
                "#3b82f6",
                "#f59e0b",
                "#10b981",
                "#ef4444",
            ]
        );
    }


    // =========================================================
    // DATA COLLECTION DONUT
    // =========================================================

    getDataCollectionChartStyle() {

        if (!this.state.data) {
            return "";
        }

        return this.createDonutStyle(
            this.state.data.data_collection.chart,
            [
                "#3b82f6",
                "#f59e0b",
                "#10b981",
                "#8b5cf6",
            ]
        );
    }


    // =========================================================
    // DONUT HELPER
    // =========================================================

    createDonutStyle(data, colors) {

        const total = data.reduce(
            (sum, item) => sum + item.count,
            0
        );

        if (!total) {
            return "background: #e9ecef;";
        }

        let current = 0;

        const parts = [];

        data.forEach((item, index) => {

            const percentage =
                (item.count / total) * 100;

            const start = current;
            const end = current + percentage;

            parts.push(
                `${colors[index]} ${start}% ${end}%`
            );

            current = end;
        });

        return `background: conic-gradient(${parts.join(", ")});`;
    }


    // =========================================================
    // DEPARTMENT BAR CHART
    // =========================================================

    getBarHeight(count) {

        if (!this.state.data) {
            return 0;
        }

        const departments =
            this.state.data.departments;

        const max = Math.max(
            ...departments.map(
                item => item.count
            ),
            1
        );

        return Math.max(
            (count / max) * 100,
            count > 0 ? 8 : 2
        );
    }


    // =========================================================
    // PIPELINE BAR
    // =========================================================

    getPipelineWidth(count) {

        if (!this.state.data) {
            return 0;
        }

        const max = Math.max(
            ...this.state.data.stages.map(
                stage => stage.count
            ),
            1
        );

        return Math.max(
            (count / max) * 100,
            count > 0 ? 5 : 0
        );
    }


    // =========================================================
    // OPEN PROJECTS
    // =========================================================

    async openProjects() {

        const domain = [];

        if (this.state.departmentId) {

            domain.push([
                "department_id",
                "=",
                this.state.departmentId,
            ]);
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Business Projects",
            res_model: "business.project",

            views: [
                [false, "kanban"],
                [false, "list"],
                [false, "form"],
            ],

            domain: domain,
        });
    }


    // =========================================================
    // OPEN STAGE
    // =========================================================

    async openStage(stageId) {

        const domain = [
            [
                "stage_id",
                "=",
                stageId
            ]
        ];

        if (this.state.departmentId) {

            domain.push([
                "department_id",
                "=",
                this.state.departmentId,
            ]);
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Business Projects",
            res_model: "business.project",

            views: [
                [false, "kanban"],
                [false, "list"],
                [false, "form"],
            ],

            domain: domain,
        });
    }


    // =========================================================
    // OPEN KRAs
    // =========================================================

    async openKras() {

        const domain = [];

        if (this.state.departmentId) {

            domain.push([
                "project_id.department_id",
                "=",
                this.state.departmentId,
            ]);
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Project KRAs",
            res_model: "business.project.kra",

            views: [
                [false, "list"],
                [false, "form"],
            ],

            domain: domain,
        });
    }


    // =========================================================
    // OPEN ACTIVITIES
    // =========================================================

    async openActivities() {

        const domain = [];

        if (this.state.departmentId) {

            domain.push([
                "project_id.department_id",
                "=",
                this.state.departmentId,
            ]);
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Project Activities",
            res_model: "business.project.activity",

            views: [
                [false, "list"],
                [false, "form"],
            ],

            domain: domain,
        });
    }


    // =========================================================
    // OPEN DATA COLLECTION
    // =========================================================

    async openDataCollection() {

        const domain = [];

        if (this.state.departmentId) {

            domain.push([
                "project_id.department_id",
                "=",
                this.state.departmentId,
            ]);
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Data Collection",
            res_model: "business.project.data.collection",

            views: [
                [false, "list"],
                [false, "form"],
            ],

            domain: domain,
        });
    }


    // =========================================================
    // OPEN CRM
    // =========================================================

    async openCRM() {

        const domain = [];

        if (this.state.departmentId) {

            domain.push([
                "department_id",
                "=",
                this.state.departmentId,
            ]);
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "CRM Leads",
            res_model: "crm.lead",

            views: [
                [false, "list"],
                [false, "form"],
            ],

            domain: domain,
        });
    }
}


registry.category("actions").add(
    "benjali_management_dashboard",
    BenjaliDashboard
);
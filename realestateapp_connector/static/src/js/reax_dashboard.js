/** @odoo-module **/
//
// The RealEstateApp Overview — an OWL client action, not a form view: cards, charts and drill-downs
// in the app's own visual language. All figures arrive in ONE rpc (reax.dashboard.get_dashboard_data),
// computed live server-side, and every card and chart segment opens the exact list it counted — the
// drill-down methods on reax.dashboard are the single source of both the number and the list.
//
// Chart.js is Odoo's own charting library (its graph views run on it); loadBundle just pulls the
// bundle web already ships. No new dependency.

import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle, loadJS } from "@web/core/assets";

// The app's palette (src/styles/global.css literals, same as settings.scss).
const INK = "#141326";
const MUTED = "#5a6076";
const INDIGO = "#1d0e7f";
const CRIMSON = "#e11d48";
const GREEN = "#0e9f6e";
const AMBER = "#c27803";
const RED = "#e02424";
const WHEEL = [INDIGO, CRIMSON, GREEN, AMBER, "#6366f1", "#0ea5e9", "#a855f7", "#64748b"];

const nf = new Intl.NumberFormat("en-US");
const nf2 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export class ReaxDashboard extends Component {
    static template = "realestateapp_connector.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, asofLabel: "", refreshing: false });
        this.charts = {};
        this.canvasMonthly = useRef("canvasMonthly");
        this.canvasOccupancy = useRef("canvasOccupancy");
        this.canvasLeads = useRef("canvasLeads");
        this.canvasMaintenance = useRef("canvasMaintenance");

        onWillStart(async () => {
            // This deployment's web.chart_lib bundle answers [] even though the library file itself
            // ships (v4.4.1 at the path below) — so fall back to loading the file directly.
            await loadBundle("web.chart_lib").catch(() => {});
            if (typeof window.Chart === "undefined") {
                await loadJS("/web/static/lib/Chart/Chart.js");
            }
            await this.load();
        });
        onMounted(() => {
            this.renderCharts();
            // Live means live: repaint from the server every two minutes while the screen is open.
            this.timer = setInterval(() => this.refresh(), 120_000);
        });
        onWillUnmount(() => {
            clearInterval(this.timer);
            for (const c of Object.values(this.charts)) {
                c.destroy();
            }
        });
    }

    async load() {
        this.state.data = await this.orm.call("reax.dashboard", "get_dashboard_data", []);
        const asof = new Date(this.state.data.asof + "Z");
        this.state.asofLabel = asof.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    async refresh() {
        if (this.state.refreshing) {
            return;
        }
        this.state.refreshing = true;
        try {
            await this.load();
            this.renderCharts();
        } finally {
            this.state.refreshing = false;
        }
    }

    // ---- formatting ------------------------------------------------------------------------------
    int(v) {
        return nf.format(v || 0);
    }
    money(v) {
        return `${this.state.data.currency} ${nf2.format(v || 0)}`;
    }
    moneyShort(v) {
        const a = Math.abs(v || 0);
        if (a >= 1e6) {
            return `${(v / 1e6).toFixed(1)}M`;
        }
        if (a >= 1e3) {
            return `${(v / 1e3).toFixed(0)}k`;
        }
        return `${v}`;
    }
    monthLabel(iso) {
        return new Date(iso + "T00:00:00").toLocaleDateString("en", { month: "short", year: "2-digit" });
    }

    // ---- the cards, as data the template loops over ------------------------------------------------
    get kpis() {
        const s = this.state.data.stats;
        return [
            { icon: "fa-building", label: "Properties", value: this.int(s.properties_total), method: "action_properties" },
            { icon: "fa-th", label: "Units", value: this.int(s.units_total), sub: `${this.int(s.units_occupied)} occupied · ${this.int(s.units_vacant)} vacant`, method: "action_units" },
            { icon: "fa-pie-chart", label: "Occupancy", value: `${s.occupancy_pct.toFixed(1)}%`, sub: `${this.int(s.units_occupied)} of ${this.int(s.units_total)} units`, method: "action_units_occupied", tone: "indigo" },
            { icon: "fa-handshake-o", label: "Active Contracts", value: this.int(s.contracts_active), method: "action_contracts_active" },
            { icon: "fa-hourglass-half", label: "Expiring ≤ 60 days", value: this.int(s.contracts_expiring_60), method: "action_contracts_expiring", tone: "amber" },
            { icon: "fa-wrench", label: "Open Maintenance", value: this.int(s.maintenance_open), method: "action_maintenance_open", tone: s.maintenance_open ? "amber" : "" },
        ];
    }

    get moneyCards() {
        const s = this.state.data.stats;
        const c = this.state.data.counts;
        return [
            { icon: "fa-file-text", label: "Invoiced", value: this.money(s.inv_total), sub: `${this.int(s.inv_count)} rent invoices, all posted`, method: "action_invoices", tone: "indigo" },
            { icon: "fa-check-circle", label: "Collected", value: this.money(s.inv_paid), sub: `${this.int(c.paid)} invoices paid`, method: "action_paid", tone: "green" },
            { icon: "fa-exclamation-circle", label: "Open", value: this.money(s.inv_open), sub: `${this.int(c.open)} awaiting payment`, method: "action_collections", tone: "amber" },
            { icon: "fa-ban", label: "Bounced Cheques", value: this.int(s.inv_bounced), sub: "flagged on the invoice ref", method: "action_bounced", tone: "red" },
        ];
    }

    get leasingCards() {
        const s = this.state.data.stats;
        const p = this.state.data.people;
        return [
            { icon: "fa-filter", label: "Leads", value: this.int(s.leads_total), method: "action_leads" },
            { icon: "fa-trophy", label: "Won Leads", value: this.int(s.leads_won), method: "action_leads_won", tone: "green" },
            { icon: "fa-file-text-o", label: "Leasing Requests", value: this.int(s.requests_total), method: "action_requests" },
            { icon: "fa-calendar-check-o", label: "Bookings", value: this.int(s.bookings_total), method: "action_bookings" },
            { icon: "fa-refresh", label: "Renewals", value: this.int(s.renewals_total), method: "action_renewals" },
            { icon: "fa-user", label: "Tenants", value: this.int(p.tenants), xmlid: "realestateapp_connector.action_reax_partners_tenants" },
            { icon: "fa-user-circle-o", label: "Landlords", value: this.int(p.landlords), xmlid: "realestateapp_connector.action_reax_partners_landlords" },
            { icon: "fa-truck", label: "Vendors", value: this.int(p.vendors), xmlid: "realestateapp_connector.action_reax_partners_vendors" },
        ];
    }

    get opsRows() {
        const s = this.state.data.stats;
        return [
            { icon: "fa-gavel", label: "Open Legal Cases", value: this.int(s.legal_open), method: "action_legal_open", tone: s.legal_open ? "red" : "" },
            { icon: "fa-check-square-o", label: "Settled Cases", value: this.int(s.legal_settled), method: "action_legal_settled" },
            { icon: "fa-shield", label: "Active AMC Contracts", value: this.int(s.amc_active), method: "action_amc" },
            { icon: "fa-search", label: "Pending Inspections", value: this.int(s.inspections_pending), method: "action_inspections_pending" },
        ];
    }

    // ---- navigation --------------------------------------------------------------------------------
    async openCard(card) {
        if (card.xmlid) {
            return this.action.doAction(card.xmlid);
        }
        const act = await this.orm.call("reax.dashboard", card.method, [[this.state.data.id]]);
        if (act) {
            this.action.doAction(act);
        }
    }

    async openMonth(iso) {
        const act = await this.orm.call("reax.dashboard", "action_month_invoices", [iso]);
        if (act) {
            this.action.doAction(act);
        }
    }

    async openStatus(dataset, status) {
        const act = await this.orm.call("reax.dashboard", "action_status", [dataset, status]);
        if (act) {
            this.action.doAction(act);
        }
    }

    // ---- charts ------------------------------------------------------------------------------------
    mkChart(key, ref, config) {
        if (!ref.el) {
            return;
        }
        if (this.charts[key]) {
            this.charts[key].destroy();
        }
        this.charts[key] = new Chart(ref.el, config);
    }

    renderCharts() {
        const d = this.state.data;
        if (!d) {
            return;
        }
        const base = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, color: MUTED, font: { size: 11 } } },
            },
        };

        const months = d.charts.monthly;
        this.mkChart("monthly", this.canvasMonthly, {
            type: "bar",
            data: {
                labels: months.map((m) => this.monthLabel(m.month)),
                datasets: [
                    { label: "Invoiced", data: months.map((m) => m.invoiced), backgroundColor: INDIGO, borderRadius: 5, maxBarThickness: 26 },
                    { label: "Collected", data: months.map((m) => m.collected), backgroundColor: GREEN, borderRadius: 5, maxBarThickness: 26 },
                ],
            },
            options: {
                ...base,
                onClick: (evt, els) => els.length && this.openMonth(months[els[0].index].month),
                scales: {
                    x: { grid: { display: false }, ticks: { color: MUTED, font: { size: 11 } } },
                    y: { grid: { color: "rgba(128,134,160,.14)" }, ticks: { color: MUTED, font: { size: 11 }, callback: (v) => this.moneyShort(v) } },
                },
                plugins: {
                    ...base.plugins,
                    tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${this.money(c.raw)} (${this.int(months[c.dataIndex].count)} invoices)` } },
                },
            },
        });

        const occ = d.charts.occupancy;
        this.mkChart("occupancy", this.canvasOccupancy, {
            type: "doughnut",
            data: {
                labels: occ.map((r) => r.label),
                datasets: [{ data: occ.map((r) => r.value), backgroundColor: occ.map((_, i) => WHEEL[i % WHEEL.length]), borderWidth: 2, borderColor: "#ffffff" }],
            },
            options: {
                ...base,
                cutout: "68%",
                onClick: (evt, els) => els.length && this.openStatus("occupancy", occ[els[0].index].label),
            },
        });

        // Top seven lead statuses, the tail bucketed — eight bars stay readable, thirty don't.
        const leadsAll = d.charts.leads;
        const leads = leadsAll.slice(0, 7);
        const rest = leadsAll.slice(7).reduce((a, r) => a + r.value, 0);
        if (rest) {
            leads.push({ label: "Other", value: rest });
        }
        this.mkChart("leads", this.canvasLeads, {
            type: "bar",
            data: {
                labels: leads.map((r) => r.label),
                datasets: [{ label: "Leads", data: leads.map((r) => r.value), backgroundColor: CRIMSON, borderRadius: 5, maxBarThickness: 18 }],
            },
            options: {
                ...base,
                indexAxis: "y",
                onClick: (evt, els) => {
                    const row = els.length && leads[els[0].index];
                    if (row && row.label !== "Other") {
                        this.openStatus("leads", row.label);
                    }
                },
                plugins: { ...base.plugins, legend: { display: false } },
                scales: {
                    x: { grid: { color: "rgba(128,134,160,.14)" }, ticks: { color: MUTED, font: { size: 11 } } },
                    y: { grid: { display: false }, ticks: { color: INK, font: { size: 11 } } },
                },
            },
        });

        const maint = d.charts.maintenance;
        this.mkChart("maintenance", this.canvasMaintenance, {
            type: "doughnut",
            data: {
                labels: maint.map((r) => r.label),
                datasets: [{ data: maint.map((r) => r.value), backgroundColor: maint.map((_, i) => WHEEL[(i + 2) % WHEEL.length]), borderWidth: 2, borderColor: "#ffffff" }],
            },
            options: {
                ...base,
                cutout: "68%",
                onClick: (evt, els) => els.length && this.openStatus("maintenance", maint[els[0].index].label),
            },
        });
    }
}

registry.category("actions").add("reax_dashboard", ReaxDashboard);

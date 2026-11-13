
"use strict";

/*
 * FloodShield Citizen Management
 *
 * Uses:
 * GET /api/admin/citizens
 * GET /api/admin/citizens/<citizen_id>
 *
 * This module is read-only. It does not expose password hashes,
 * Firebase UIDs, or private authentication credentials.
 */

(() => {
    const DIRECTORY_API = "/api/admin/citizens";
    const PAGE_SIZE = 10;
    const DETAIL_PAGE_SIZE = 10;

    const state = {
        page: 1,
        totalPages: 0,
        search: "",
        currentCitizenId: null,
        detailPage: 1,
        detailTotalPages: 0,
        loading: false
    };

    const $ = id => document.getElementById(id);

    function escapeText(value) {
        if (value === null || value === undefined || value === "") {
            return "—";
        }

        return String(value);
    }

    function formatDate(value) {
        if (!value) return "—";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return "—";
        }

        return date.toLocaleString();
    }

    function createCell(value, className = "") {
        const cell = document.createElement("td");

        cell.textContent = escapeText(value);

        if (className) {
            cell.className = className;
        }

        return cell;
    }

    function createBadge(value, className) {
        const badge = document.createElement("span");

        badge.className = `badge ${className}`;
        badge.textContent = value;

        return badge;
    }

    function renderMessage(body, message, columns, className = "") {
        body.replaceChildren();

        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = columns;
        cell.className = `text-center py-4 ${className}`.trim();
        cell.textContent = message;

        row.appendChild(cell);
        body.appendChild(row);
    }

    async function apiGet(url) {
        const response = await fetch(url, {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json"
            }
        });

        let result;

        try {
            result = await response.json();
        } catch {
            throw new Error("The server returned an invalid response.");
        }

        if (response.status === 401 || response.status === 422) {
            window.location.href = "/admin/login";
            throw new Error("Administrator session expired.");
        }

        if (!response.ok || result.status !== "success") {
            throw new Error(
                result.message || "Unable to retrieve citizen information."
            );
        }

        return result;
    }

    function buildInterface() {
        const navigation = $("dashboardTabs");
        const tabContent = document.querySelector(".tab-content");

        if (!navigation || !tabContent) {
            return false;
        }

        if ($("citizensPanel")) {
            return true;
        }

        const navItem = document.createElement("li");
        navItem.className = "nav-item";
        navItem.setAttribute("role", "presentation");

        const navButton = document.createElement("button");
        navButton.type = "button";
        navButton.className = "nav-link";
        navButton.id = "citizensTab";
        navButton.dataset.bsToggle = "pill";
        navButton.dataset.bsTarget = "#citizensPanel";
        navButton.setAttribute("role", "tab");
        navButton.setAttribute("aria-controls", "citizensPanel");
        navButton.setAttribute("aria-selected", "false");
        navButton.textContent = "Citizens";

        navItem.appendChild(navButton);
        navigation.appendChild(navItem);

        const panel = document.createElement("section");
        panel.className = "tab-pane fade";
        panel.id = "citizensPanel";
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", "citizensTab");

        panel.innerHTML = `
            <div class="d-flex flex-wrap justify-content-between
                        align-items-center gap-3 mb-4">
                <div>
                    <h3 class="mb-1">Citizen Management</h3>
                    <p class="text-muted mb-0">
                        View registered citizens and their flood report history.
                    </p>
                </div>

                <button
                    type="button"
                    class="btn btn-outline-primary"
                    id="refreshCitizensButton"
                >
                    Refresh Citizens
                </button>
            </div>

            <div class="card dashboard-card mb-4">
                <div class="card-body">
                    <form id="citizenSearchForm"
                          class="row g-3 align-items-end">

                        <div class="col-12 col-md-8">
                            <label
                                for="citizenSearchInput"
                                class="form-label"
                            >
                                Search citizens
                            </label>

                            <input
                                type="search"
                                class="form-control"
                                id="citizenSearchInput"
                                maxlength="120"
                                placeholder="Search by name, email or phone number"
                            >
                        </div>

                        <div class="col-6 col-md-2">
                            <button
                                type="submit"
                                class="btn btn-primary w-100"
                                id="citizenSearchButton"
                            >
                                Search
                            </button>
                        </div>

                        <div class="col-6 col-md-2">
                            <button
                                type="button"
                                class="btn btn-outline-secondary w-100"
                                id="citizenResetButton"
                            >
                                Reset
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <div class="d-flex justify-content-between
                        align-items-center mb-3">
                <span
                    class="text-muted"
                    id="citizenResultSummary"
                    aria-live="polite"
                >
                    Loading citizens...
                </span>

                <span class="small text-muted">
                    Page size: ${PAGE_SIZE}
                </span>
            </div>

            <div class="card dashboard-card">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Phone</th>
                                <th>Reports</th>
                                <th>Firebase Auth</th>
                                <th>Joined</th>
                                <th>Action</th>
                            </tr>
                        </thead>

                        <tbody id="citizenTableBody">
                            <tr>
                                <td colspan="8"
                                    class="text-center py-4">
                                    Loading citizens...
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <div class="card-body border-top
                            d-flex flex-wrap justify-content-between
                            align-items-center gap-3">

                    <span
                        class="text-muted small"
                        id="citizenPaginationInfo"
                    ></span>

                    <div class="d-flex gap-2">
                        <button
                            type="button"
                            class="btn btn-outline-secondary btn-sm"
                            id="citizenPreviousButton"
                            disabled
                        >
                            Previous
                        </button>

                        <button
                            type="button"
                            class="btn btn-outline-secondary btn-sm"
                            id="citizenNextButton"
                            disabled
                        >
                            Next
                        </button>
                    </div>
                </div>
            </div>

            <div
                class="modal fade"
                id="citizenDetailsModal"
                tabindex="-1"
                aria-hidden="true"
            >
                <div class="modal-dialog modal-xl modal-dialog-scrollable">
                    <div class="modal-content">

                        <div class="modal-header">
                            <div>
                                <h5 class="modal-title">
                                    Citizen Profile
                                </h5>

                                <p
                                    class="text-muted small mb-0"
                                    id="citizenDetailsSubtitle"
                                ></p>
                            </div>

                            <button
                                type="button"
                                class="btn-close"
                                data-bs-dismiss="modal"
                                aria-label="Close"
                            ></button>
                        </div>

                        <div class="modal-body">
                            <div
                                id="citizenDetailsLoading"
                                class="text-center py-4"
                            >
                                Loading citizen profile...
                            </div>

                            <div
                                id="citizenDetailsContent"
                                class="d-none"
                            >
                                <div class="row g-3 mb-4">
                                    <div class="col-12 col-md-3">
                                        <div class="card h-100">
                                            <div class="card-body">
                                                <p class="text-muted mb-1">
                                                    Total Reports
                                                </p>
                                                <h3 id="citizenTotalReports">
                                                    0
                                                </h3>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="col-12 col-md-3">
                                        <div class="card h-100">
                                            <div class="card-body">
                                                <p class="text-muted mb-1">
                                                    Pending
                                                </p>
                                                <h3
                                                    class="text-warning"
                                                    id="citizenPendingReports"
                                                >
                                                    0
                                                </h3>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="col-12 col-md-3">
                                        <div class="card h-100">
                                            <div class="card-body">
                                                <p class="text-muted mb-1">
                                                    Verified
                                                </p>
                                                <h3
                                                    class="text-success"
                                                    id="citizenVerifiedReports"
                                                >
                                                    0
                                                </h3>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="col-12 col-md-3">
                                        <div class="card h-100">
                                            <div class="card-body">
                                                <p class="text-muted mb-1">
                                                    Rejected
                                                </p>
                                                <h3
                                                    class="text-danger"
                                                    id="citizenRejectedReports"
                                                >
                                                    0
                                                </h3>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <h6 class="mb-3">Citizen Information</h6>

                                <div class="table-responsive mb-4">
                                    <table class="table table-bordered">
                                        <tbody id="citizenProfileBody"></tbody>
                                    </table>
                                </div>

                                <h6 class="mb-3">Flood Report History</h6>

                                <div class="table-responsive">
                                    <table class="table table-hover
                                                  align-middle">
                                        <thead>
                                            <tr>
                                                <th>Report ID</th>
                                                <th>Description</th>
                                                <th>Coordinates</th>
                                                <th>Water Depth</th>
                                                <th>Status</th>
                                                <th>Submitted</th>
                                            </tr>
                                        </thead>

                                        <tbody id="citizenReportsBody"></tbody>
                                    </table>
                                </div>

                                <div class="d-flex flex-wrap
                                            justify-content-between
                                            align-items-center gap-2 mt-3">

                                    <span
                                        class="small text-muted"
                                        id="citizenReportPaginationInfo"
                                    ></span>

                                    <div class="d-flex gap-2">
                                        <button
                                            type="button"
                                            class="btn btn-outline-secondary btn-sm"
                                            id="citizenReportsPrevious"
                                            disabled
                                        >
                                            Previous
                                        </button>

                                        <button
                                            type="button"
                                            class="btn btn-outline-secondary btn-sm"
                                            id="citizenReportsNext"
                                            disabled
                                        >
                                            Next
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <div
                                id="citizenDetailsError"
                                class="alert alert-danger d-none mt-3"
                                role="alert"
                            ></div>
                        </div>

                        <div class="modal-footer">
                            <button
                                type="button"
                                class="btn btn-secondary"
                                data-bs-dismiss="modal"
                            >
                                Close
                            </button>
                        </div>

                    </div>
                </div>
            </div>
        `;

        tabContent.appendChild(panel);

        return true;
    }

    function renderCitizens(citizens) {
        const body = $("citizenTableBody");

        if (!Array.isArray(citizens) || citizens.length === 0) {
            renderMessage(
                body,
                "No citizens found.",
                8
            );
            return;
        }

        body.replaceChildren();

        citizens.forEach(citizen => {
            const row = document.createElement("tr");

            row.appendChild(createCell(citizen.id));
            row.appendChild(createCell(citizen.name));
            row.appendChild(createCell(citizen.email));
            row.appendChild(createCell(citizen.phone_number));
            row.appendChild(createCell(citizen.report_count ?? 0));

            const firebaseCell = document.createElement("td");

            firebaseCell.appendChild(
                citizen.firebase_linked
                    ? createBadge("Linked", "bg-success")
                    : createBadge("Not linked", "bg-secondary")
            );

            row.appendChild(firebaseCell);
            row.appendChild(createCell(formatDate(citizen.created_at)));

            const actionCell = document.createElement("td");
            const button = document.createElement("button");

            button.type = "button";
            button.className = "btn btn-outline-primary btn-sm";
            button.textContent = "View Profile";
            button.dataset.citizenId = citizen.id;

            actionCell.appendChild(button);
            row.appendChild(actionCell);

            body.appendChild(row);
        });
    }

    async function loadCitizens() {
        if (state.loading) return;

        state.loading = true;

        const body = $("citizenTableBody");

        renderMessage(body, "Loading citizens...", 8);

        $("citizenSearchButton").disabled = true;
        $("refreshCitizensButton").disabled = true;

        try {
            const params = new URLSearchParams({
                page: String(state.page),
                per_page: String(PAGE_SIZE)
            });

            if (state.search) {
                params.set("search", state.search);
            }

            const result = await apiGet(
                `${DIRECTORY_API}?${params.toString()}`
            );

            const pagination = result.pagination || {};

            state.totalPages = Number(
                pagination.total_pages || 0
            );

            renderCitizens(result.citizens || []);

            $("citizenResultSummary").textContent =
                `${pagination.total_records ?? 0} citizen(s) found`;

            $("citizenPaginationInfo").textContent =
                state.totalPages
                    ? `Page ${pagination.page || state.page} of ${state.totalPages}`
                    : "No pages";

            $("citizenPreviousButton").disabled =
                state.page <= 1;

            $("citizenNextButton").disabled =
                !state.totalPages ||
                state.page >= state.totalPages;

        } catch (error) {
            renderMessage(
                body,
                error.message,
                8,
                "text-danger"
            );

            $("citizenResultSummary").textContent =
                "Unable to load citizens.";

            $("citizenPaginationInfo").textContent = "";

            $("citizenPreviousButton").disabled = true;
            $("citizenNextButton").disabled = true;

        } finally {
            state.loading = false;

            $("citizenSearchButton").disabled = false;
            $("refreshCitizensButton").disabled = false;
        }
    }

    function renderCitizenProfile(citizen) {
        const body = $("citizenProfileBody");
        body.replaceChildren();

        const fields = [
            ["Citizen ID", citizen.id],
            ["Name", citizen.name],
            ["Email", citizen.email],
            ["Phone Number", citizen.phone_number],
            ["Role", citizen.role],
            ["Account Created", formatDate(citizen.created_at)],
            [
                "Firebase Authentication",
                citizen.firebase_linked ? "Linked" : "Not linked"
            ]
        ];

        fields.forEach(([label, value]) => {
            const row = document.createElement("tr");
            const heading = document.createElement("th");

            heading.textContent = label;
            heading.scope = "row";

            row.appendChild(heading);
            row.appendChild(createCell(value));

            body.appendChild(row);
        });
    }

    function renderCitizenReports(reports) {
        const body = $("citizenReportsBody");

        if (!Array.isArray(reports) || reports.length === 0) {
            renderMessage(
                body,
                "This citizen has not submitted any reports.",
                6
            );
            return;
        }

        body.replaceChildren();

        reports.forEach(report => {
            const row = document.createElement("tr");

            row.appendChild(createCell(`#${report.id}`));

            row.appendChild(
                createCell(
                    report.description || "No description"
                )
            );

            row.appendChild(
                createCell(
                    `${report.latitude ?? "—"}, ${report.longitude ?? "—"}`
                )
            );

            row.appendChild(
                createCell(
                    report.water_depth_cm == null
                        ? "Not provided"
                        : `${report.water_depth_cm} cm`
                )
            );

            const statusCell = document.createElement("td");

            const statusClasses = {
                pending: "bg-warning text-dark",
                verified: "bg-success",
                rejected: "bg-danger"
            };

            const status = String(report.status || "").toLowerCase();

            statusCell.appendChild(
                createBadge(
                    status || "Unknown",
                    statusClasses[status] || "bg-secondary"
                )
            );

            row.appendChild(statusCell);
            row.appendChild(createCell(formatDate(report.created_at)));

            body.appendChild(row);
        });
    }

    async function loadCitizenDetails() {
        if (!state.currentCitizenId) return;

        $("citizenDetailsLoading").classList.remove("d-none");
        $("citizenDetailsContent").classList.add("d-none");
        $("citizenDetailsError").classList.add("d-none");

        try {
            const params = new URLSearchParams({
                page: String(state.detailPage),
                per_page: String(DETAIL_PAGE_SIZE)
            });

            const result = await apiGet(
                `${DIRECTORY_API}/${state.currentCitizenId}?${params.toString()}`
            );

            const citizen = result.citizen || {};
            const summary = result.report_summary || {};
            const pagination = result.pagination || {};

            $("citizenDetailsSubtitle").textContent =
                `${citizen.name || "Citizen"} · ID ${citizen.id}`;

            $("citizenTotalReports").textContent =
                summary.total ?? 0;

            $("citizenPendingReports").textContent =
                summary.pending ?? 0;

            $("citizenVerifiedReports").textContent =
                summary.verified ?? 0;

            $("citizenRejectedReports").textContent =
                summary.rejected ?? 0;

            renderCitizenProfile(citizen);
            renderCitizenReports(result.reports || []);

            state.detailTotalPages = Number(
                pagination.total_pages || 0
            );

            $("citizenReportPaginationInfo").textContent =
                state.detailTotalPages
                    ? `Page ${pagination.page || state.detailPage} of ${state.detailTotalPages}`
                    : "No report pages";

            $("citizenReportsPrevious").disabled =
                state.detailPage <= 1;

            $("citizenReportsNext").disabled =
                !state.detailTotalPages ||
                state.detailPage >= state.detailTotalPages;

            $("citizenDetailsLoading").classList.add("d-none");
            $("citizenDetailsContent").classList.remove("d-none");

        } catch (error) {
            $("citizenDetailsLoading").classList.add("d-none");

            const errorElement = $("citizenDetailsError");
            errorElement.textContent = error.message;
            errorElement.classList.remove("d-none");
        }
    }

    async function openCitizenDetails(citizenId) {
        const id = Number(citizenId);

        if (!Number.isInteger(id) || id <= 0) {
            return;
        }

        state.currentCitizenId = id;
        state.detailPage = 1;

        const modalElement = $("citizenDetailsModal");

        const modal = bootstrap.Modal.getOrCreateInstance(
            modalElement
        );

        modal.show();

        await loadCitizenDetails();
    }

    function bindEvents() {
        $("citizenSearchForm").addEventListener(
            "submit",
            event => {
                event.preventDefault();

                state.search = $("citizenSearchInput").value.trim();
                state.page = 1;

                loadCitizens();
            }
        );

        $("citizenResetButton").addEventListener(
            "click",
            () => {
                $("citizenSearchInput").value = "";

                state.search = "";
                state.page = 1;

                loadCitizens();
            }
        );

        $("refreshCitizensButton").addEventListener(
            "click",
            loadCitizens
        );

        $("citizenPreviousButton").addEventListener(
            "click",
            () => {
                if (state.page > 1) {
                    state.page--;
                    loadCitizens();
                }
            }
        );

        $("citizenNextButton").addEventListener(
            "click",
            () => {
                if (state.page < state.totalPages) {
                    state.page++;
                    loadCitizens();
                }
            }
        );

        $("citizenTableBody").addEventListener(
            "click",
            event => {
                const button = event.target.closest(
                    "[data-citizen-id]"
                );

                if (button) {
                    openCitizenDetails(
                        button.dataset.citizenId
                    );
                }
            }
        );

        $("citizenReportsPrevious").addEventListener(
            "click",
            () => {
                if (state.detailPage > 1) {
                    state.detailPage--;
                    loadCitizenDetails();
                }
            }
        );

        $("citizenReportsNext").addEventListener(
            "click",
            () => {
                if (state.detailPage < state.detailTotalPages) {
                    state.detailPage++;
                    loadCitizenDetails();
                }
            }
        );

        $("citizensTab").addEventListener(
            "shown.bs.tab",
            () => {
                loadCitizens();
            }
        );
    }

    function initialize() {
        if (!buildInterface()) {
            return;
        }

        bindEvents();
    }

    document.addEventListener("DOMContentLoaded", initialize);
})();

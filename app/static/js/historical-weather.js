"use strict";

(() => {
    const API_URL = "/api/historical-weather";

    const state = {
        page: 1,
        totalPages: 0,
        loading: false,
        requestNumber: 0,
        detailRequestNumber: 0,
        initialized: false,
        loaded: false,
        pagination: {
            total_records: 0,
            total_pages: 0
        }
    };

    const $ = id => document.getElementById(id);


    // Formats an ISO date or datetime for display.
    function formatDate(value) {
        if (!value) return "Unavailable";

        const date = new Date(value);

        return Number.isNaN(date.getTime())
            ? "Unavailable"
            : date.toLocaleString();
    }


    // Creates a table cell without interpreting API values as HTML.
    function createCell(value, className = "") {
        const cell = document.createElement("td");

        cell.textContent =
            value === undefined ||
            value === null ||
            value === ""
                ? "—"
                : String(value);

        if (className) {
            cell.className = className;
        }

        return cell;
    }


    // Displays an error message.
    function showError(message) {
        const box = $("historicalWeatherError");

        box.textContent =
            message || "Unable to load historical weather.";

        box.classList.remove("d-none");
    }


    // Clears the displayed error.
    function clearError() {
        const box = $("historicalWeatherError");

        box.textContent = "";
        box.classList.add("d-none");
    }


    // Reads and validates historical weather search filters.
    function readFilters() {
        const start = $("historicalWeatherStart").value;
        const end = $("historicalWeatherEnd").value;

        const latitudeText =
            $("historicalWeatherLatitude").value.trim();

        const longitudeText =
            $("historicalWeatherLongitude").value.trim();

        const radiusText =
            $("historicalWeatherRadius").value.trim();

        if (start && end && start > end) {
            throw new Error(
                "Start date must not be after end date."
            );
        }

        const locationValues = [
            latitudeText,
            longitudeText,
            radiusText
        ];

        const anyLocationValue =
            locationValues.some(Boolean);

        const allLocationValues =
            locationValues.every(Boolean);

        if (anyLocationValue && !allLocationValues) {
            throw new Error(
                "Enter latitude, longitude and radius together."
            );
        }

        const filters = {
            start_date: start,
            end_date: end
        };

        if (allLocationValues) {
            const latitude = Number(latitudeText);
            const longitude = Number(longitudeText);
            const radius = Number(radiusText);

            if (
                !Number.isFinite(latitude) ||
                latitude < -90 ||
                latitude > 90
            ) {
                throw new Error(
                    "Latitude must be between -90 and 90."
                );
            }

            if (
                !Number.isFinite(longitude) ||
                longitude < -180 ||
                longitude > 180
            ) {
                throw new Error(
                    "Longitude must be between -180 and 180."
                );
            }

            if (
                !Number.isFinite(radius) ||
                radius <= 0
            ) {
                throw new Error(
                    "Radius must be a positive number."
                );
            }

            filters.latitude = latitude;
            filters.longitude = longitude;
            filters.radius_km = radius;
        }

        return filters;
    }


    // Displays detailed information about one weather observation.
    function renderDetails(record) {
        const panel = $("historicalWeatherDetailsPanel");
        const content = $("historicalWeatherDetailsContent");

        content.replaceChildren();

        const fields = [
            ["Record ID", record.id],
            ["Recorded at", formatDate(record.recorded_at)],
            ["Latitude", record.latitude],
            ["Longitude", record.longitude],
            [
                "Temperature",
                record.temperature_c == null
                    ? "Unavailable"
                    : `${record.temperature_c} °C`
            ],
            [
                "Rainfall",
                record.rainfall_mm == null
                    ? "Unavailable"
                    : `${record.rainfall_mm} mm`
            ],
            [
                "Precipitation interval",
                record.precipitation_interval_seconds == null
                    ? "Unavailable"
                    : `${record.precipitation_interval_seconds} seconds`
            ],
            [
                "Wind speed",
                record.wind_speed_kmh == null
                    ? "Unavailable"
                    : `${record.wind_speed_kmh} km/h`
            ],
            ["Weather code", record.weather_code],
            ["Source", record.source],
            ["Created at", formatDate(record.created_at)]
        ];

        const list = document.createElement("dl");
        list.className = "row mb-0";

        fields.forEach(([label, value]) => {
            if (value === undefined) return;

            const term = document.createElement("dt");
            term.className = "col-sm-4";
            term.textContent = label;

            const description = document.createElement("dd");
            description.className = "col-sm-8";

            description.textContent =
                value === null || value === ""
                    ? "Unavailable"
                    : String(value);

            list.append(term, description);
        });

        content.appendChild(list);

        panel.classList.remove("d-none");

        panel.scrollIntoView({
            behavior: "smooth",
            block: "nearest"
        });
    }


    // Fetches and displays one historical weather record.
    async function openDetails(id) {
        const requestNumber = ++state.detailRequestNumber;

        const content = $("historicalWeatherDetailsContent");
        const panel = $("historicalWeatherDetailsPanel");

        content.textContent =
            "Loading observation details...";

        panel.classList.remove("d-none");

        try {
            const response = await fetch(
                `${API_URL}/${encodeURIComponent(id)}`,
                {
                    method: "GET",
                    headers: {
                        Accept: "application/json"
                    },
                    credentials: "same-origin"
                }
            );

            const result = await response.json().catch(
                () => ({})
            );

            if (!response.ok) {
                throw new Error(
                    result.message ||
                    `Request failed (${response.status}).`
                );
            }

            if (
                result.status !== "success" ||
                !result.data ||
                typeof result.data !== "object"
            ) {
                throw new Error(
                    "Invalid observation details response."
                );
            }

            if (
                requestNumber !== state.detailRequestNumber
            ) {
                return;
            }

            renderDetails(result.data);

        } catch (error) {
            if (
                requestNumber !== state.detailRequestNumber
            ) {
                return;
            }

            content.textContent =
                error.message ||
                "Unable to load observation details.";
        }
    }


    // Displays historical weather observations in the table.
    function renderRows(records) {
        const body = $("historicalWeatherTableBody");

        body.replaceChildren();

        if (!records.length) {
            const row = document.createElement("tr");

            const cell = createCell(
                "No historical weather observations found.",
                "table-message"
            );

            cell.colSpan = 9;

            row.appendChild(cell);
            body.appendChild(row);

            return;
        }

        records.forEach(record => {
            const row = document.createElement("tr");

            row.appendChild(createCell(record.id));

            row.appendChild(
                createCell(formatDate(record.recorded_at))
            );

            row.appendChild(
                createCell(
                    record.temperature_c == null
                        ? "—"
                        : `${record.temperature_c} °C`
                )
            );

            row.appendChild(
                createCell(
                    record.rainfall_mm == null
                        ? "—"
                        : `${record.rainfall_mm} mm`
                )
            );

            row.appendChild(
                createCell(
                    record.wind_speed_kmh == null
                        ? "—"
                        : `${record.wind_speed_kmh} km/h`
                )
            );

            row.appendChild(
                createCell(record.weather_code)
            );

            row.appendChild(
                createCell(
                    `${record.latitude ?? "—"}, ${record.longitude ?? "—"}`
                )
            );

            row.appendChild(
                createCell(record.source)
            );

            const action = document.createElement("td");
            const button = document.createElement("button");

            button.type = "button";
            button.className = "btn btn-outline-primary btn-sm";
            button.textContent = "Details";
            button.dataset.observationId = record.id;

            action.appendChild(button);
            row.appendChild(action);

            body.appendChild(row);
        });
    }


    // Updates result counts and pagination controls.
    function updatePagination() {
        const total =
            state.pagination.total_records ?? 0;

        state.totalPages =
            state.pagination.total_pages ?? 0;

        $("historicalWeatherSummary").textContent =
            `${total} historical weather observation(s) found`;

        $("historicalWeatherPaginationInfo").textContent =
            state.totalPages
                ? `Page ${state.page} of ${state.totalPages}`
                : "No pages";

        $("historicalWeatherPrevious").disabled =
            state.loading || state.page <= 1;

        $("historicalWeatherNext").disabled =
            state.loading ||
            !state.totalPages ||
            state.page >= state.totalPages;
    }


    // Loads historical weather observations from the Flask API.
    async function loadObservations() {
        if (state.loading) {
            state.requestNumber++;
        }

        const requestNumber = ++state.requestNumber;

        state.loading = true;

        clearError();

        const searchButton =
            $("historicalWeatherSearchButton");

        searchButton.disabled = true;

        $("historicalWeatherPrevious").disabled = true;
        $("historicalWeatherNext").disabled = true;

        const body = $("historicalWeatherTableBody");

        body.replaceChildren();

        const loadingRow = document.createElement("tr");

        const loadingCell = createCell(
            "Loading historical weather observations...",
            "table-message"
        );

        loadingCell.colSpan = 9;

        loadingRow.appendChild(loadingCell);
        body.appendChild(loadingRow);

        $("historicalWeatherSummary").textContent =
            "Loading observations...";

        try {
            const filters = readFilters();
            const params = new URLSearchParams();

            Object.entries(filters).forEach(
                ([key, value]) => {
                    if (
                        value !== undefined &&
                        value !== null &&
                        value !== ""
                    ) {
                        params.set(key, String(value));
                    }
                }
            );

            params.set("page", String(state.page));

            params.set(
                "per_page",
                $("historicalWeatherPageSize").value
            );

            const response = await fetch(
                `${API_URL}?${params.toString()}`,
                {
                    method: "GET",
                    headers: {
                        Accept: "application/json"
                    },
                    credentials: "same-origin"
                }
            );

            const result = await response.json().catch(
                () => ({})
            );

            if (!response.ok) {
                throw new Error(
                    result.message ||
                    `Request failed (${response.status}).`
                );
            }

            if (
                result.status !== "success" ||
                !Array.isArray(result.data) ||
                !result.pagination
            ) {
                throw new Error(
                    "Invalid historical weather response."
                );
            }

            // Ignore outdated responses from earlier searches.
            if (requestNumber !== state.requestNumber) {
                return;
            }

            state.pagination = {
                total_records:
                    result.pagination.total_records ?? 0,
                total_pages:
                    result.pagination.total_pages ?? 0
            };

            renderRows(result.data);

            state.loaded = true;

        } catch (error) {
            if (requestNumber !== state.requestNumber) {
                return;
            }

            body.replaceChildren();

            const row = document.createElement("tr");

            const cell = createCell(
                error.message ||
                "Unable to load observations.",
                "table-message text-danger"
            );

            cell.colSpan = 9;

            row.appendChild(cell);
            body.appendChild(row);

            state.pagination = {
                total_records: 0,
                total_pages: 0
            };

            showError(
                error.message ||
                "Unable to load historical weather observations."
            );

        } finally {
            if (requestNumber === state.requestNumber) {
                state.loading = false;

                searchButton.disabled = false;

                updatePagination();
            }
        }
    }


    // Connects form controls and dashboard tab events.
    function initialize() {
        if (state.initialized) return;

        state.initialized = true;

        const filterForm =
            $("historicalWeatherFilterForm");

        filterForm.addEventListener(
            "submit",
            event => {
                event.preventDefault();

                state.page = 1;
                loadObservations();
            }
        );

        $("historicalWeatherResetButton").addEventListener(
            "click",
            () => {
                filterForm.reset();

                state.page = 1;
                loadObservations();
            }
        );

        $("historicalWeatherPageSize").addEventListener(
            "change",
            () => {
                state.page = 1;
                loadObservations();
            }
        );

        $("historicalWeatherPrevious").addEventListener(
            "click",
            () => {
                if (
                    !state.loading &&
                    state.page > 1
                ) {
                    state.page--;
                    loadObservations();
                }
            }
        );

        $("historicalWeatherNext").addEventListener(
            "click",
            () => {
                if (
                    !state.loading &&
                    state.page < state.totalPages
                ) {
                    state.page++;
                    loadObservations();
                }
            }
        );

        $("historicalWeatherTableBody").addEventListener(
            "click",
            event => {
                const button = event.target.closest(
                    "[data-observation-id]"
                );

                if (button) {
                    openDetails(
                        button.dataset.observationId
                    );
                }
            }
        );

        $("historicalWeatherDetailsClose").addEventListener(
            "click",
            () => {
                state.detailRequestNumber++;

                $("historicalWeatherDetailsPanel")
                    .classList.add("d-none");
            }
        );

        document.querySelectorAll(
            "#dashboardTabs [data-bs-toggle='pill']"
        ).forEach(tab => {
            tab.addEventListener(
                "shown.bs.tab",
                event => {
                    if (
                        event.target.dataset.bsTarget ===
                        "#historicalWeatherPanel"
                    ) {
                        loadObservations();
                    }
                }
            );
        });
    }


    document.addEventListener(
        "DOMContentLoaded",
        initialize
    );
})();
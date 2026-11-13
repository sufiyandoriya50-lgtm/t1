"use strict";

document.addEventListener("DOMContentLoaded", function () {
    const collectButton = document.getElementById(
        "weatherCollectButton"
    );

    const weatherForm = document.getElementById(
        "weatherForm"
    );

    if (!collectButton || !weatherForm) return;

    // Enables collection after the main weather form succeeds.
    weatherForm.addEventListener("submit", function () {
        collectButton.disabled = true;

        window.setTimeout(() => {
            if (
                typeof state !== "undefined" &&
                state.weatherCoordinates
            ) {
                collectButton.disabled = false;
            }
        }, 0);
    });

    // Collects and saves a weather observation.
    collectButton.addEventListener("click", async function () {
        if (
            typeof state === "undefined" ||
            !state.weatherCoordinates
        ) {
            showError(
                "Load weather for valid coordinates before collecting."
            );
            return;
        }

        const originalText = collectButton.textContent;

        collectButton.disabled = true;
        collectButton.textContent = "Collecting...";

        try {
            const params = new URLSearchParams({
                latitude: String(
                    state.weatherCoordinates.latitude
                ),
                longitude: String(
                    state.weatherCoordinates.longitude
                )
            });

            const result = await apiRequest(
                `/api/weather/collect?${params.toString()}`,
                { method: "POST" }
            );

            if (
                result.status !== "success" ||
                !result.data
            ) {
                throw new Error(
                    result.message ||
                    "Weather collection failed."
                );
            }

            renderWeatherObject(
                document.getElementById("weatherLatest"),
                result.data
            );

            const recordId =
                result.data.database_record_id ??
                result.data.id ??
                "Unavailable";

            showSuccess(
                `${result.message || "Weather collected and saved."} Record ID: ${recordId}`
            );

        } catch (error) {
            showError(
                error.message || "Unable to collect weather."
            );

        } finally {
            collectButton.disabled = !state.weatherCoordinates;
            collectButton.textContent = originalText;
        }
    });
});
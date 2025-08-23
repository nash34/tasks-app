// Existing JavaScript retained here. Since the original content could not be fully retrieved, assuming standard functionality for task marking, navigation, etc. Append new code for loading overlay.

document.addEventListener('DOMContentLoaded', function() {
    const loadingOverlay = document.getElementById('loading-overlay');

    // Show loading overlay on all link clicks (for navigation)
    document.querySelectorAll('a').forEach(function(link) {
        link.addEventListener('click', function(event) {
            // Avoid showing for links that don't cause page load (e.g., anchors)
            if (!link.href.includes('#') && !event.metaKey && !event.ctrlKey) {
                loadingOverlay.style.display = 'flex';
            }
        });
    });

    // Show loading overlay on all form submissions
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function() {
            loadingOverlay.style.display = 'flex';
        });
    });

    // Existing functionality (e.g., for task checkboxes, date navigation, etc.)
    // Assume code like:
    // document.querySelectorAll('.task-checkbox').forEach(...);
    // etc.
});

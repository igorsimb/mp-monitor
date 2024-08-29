function toggleAllCheckboxes(clickEvent) {
    /*
//     Uses data-select-all="true" attribute to attach the event listener to checkboxes.
//     The script finds the closest .tab-pane ancestor of the clicked "select-all" checkbox to ensure that
//     only checkboxes within the same tab are toggled. This prevents your script from accidentally toggling checkboxes
//     in other parts of the document. This approach ensures that no matter which tab is active, clicking the "Select all"
//      checkbox in that tab will toggle only the checkboxes within its own domain.
//      */
    const currentSelectAll = clickEvent.target; // The clicked 'select-all' checkbox
    const tabPane = currentSelectAll.closest('.tab-pane'); // Find the closest .tab-pane ancestor
    const checkboxes = tabPane.querySelectorAll('input[type="checkbox"]:not([data-select-all="true"])'); // Select only checkboxes within this tabPane

    const shouldBeChecked = currentSelectAll.checked;
    checkboxes.forEach(checkbox => {
        checkbox.checked = shouldBeChecked;
    });

    // After toggling, we update the "Select All" checkbox state to reflect the current status
    updateSelectAllCheckboxState(tabPane, currentSelectAll);
}

function updateSelectAllCheckboxState(tabPane, selectAllCheckbox) {
    /*
    Keep the "Select All" checkbox in sync with the state of the individual checkboxes.
    This function is called after the checkboxes have been toggled to ensure the "Select All" checkbox accurately
    reflects the overall state.
     */
    const checkboxes = tabPane.querySelectorAll('input[type="checkbox"]:not([data-select-all="true"])');
    const allChecked = Array.from(checkboxes).every(checkbox => checkbox.checked);
    selectAllCheckbox.checked = allChecked;
}

document.addEventListener('DOMContentLoaded', () => {
    const selectAllCheckboxes = document.querySelectorAll('[data-select-all="true"]');

    // Attach the toggleAllCheckboxes function directly to the click event
    selectAllCheckboxes.forEach(selectAllCheckbox => {
        selectAllCheckbox.addEventListener('click', toggleAllCheckboxes);
    });

    // For each tab listen for changes on individual checkboxes to update the "Select All" state
    document.querySelectorAll('.tab-pane').forEach(tabPane => {
        const individualCheckboxes = tabPane.querySelectorAll('input[type="checkbox"]:not([data-select-all="true"])');
        const selectAllCheckbox = tabPane.querySelector('[data-select-all="true"]');

        individualCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => updateSelectAllCheckboxState(tabPane, selectAllCheckbox));
        });
    });
});

function limitMaxLength(input) {
    if (input.value.length > input.maxLength) {
        input.value = input.value.slice(0, input.maxLength);
    }
}


// Bootstrap tooltips
const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))


/**
 * Validates the SKUs input field and prevents form submission if it contains only whitespace or is empty.
 */
function validateSkusInput(formId, inputId, submitButtonId) {
    // Get references to important DOM elements
    const form = document.getElementById(formId);
    const skusInput = document.getElementById(inputId);
    const submitButton = document.getElementById(submitButtonId);

    /**
     * Checks if the SKUs input is valid and updates the submit button state.
     */
    function validateForm() {
        // Check if the input contains non-whitespace characters
        const isValid = skusInput.value.trim() !== '';
        // Disable the submit button if the input is invalid
        submitButton.disabled = !isValid;
    }

    // Validate the form on each input change
    skusInput.addEventListener('input', validateForm);

    // Prevent form submission if the input is invalid
    form.addEventListener('submit', function(event) {
        if (!skusInput.value.trim()) {
            event.preventDefault();
        }
    });

    // Perform initial validation
    validateForm();
}

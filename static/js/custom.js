function toggleAllCheckboxes() {
    var checkboxes = document.getElementById('table-body').getElementsByTagName('input');
    var allChecked = true;
    for (var i = 0; i < checkboxes.length; i++) {
        if (checkboxes[i].type === 'checkbox' && !checkboxes[i].checked) {
            allChecked = false;
            break;
        }
    }
    for (var i = 0; i < checkboxes.length; i++) {
        if (checkboxes[i].type === 'checkbox') {
            checkboxes[i].checked = !allChecked;
        }
    }
}

window.onload = function() {
    document.getElementById('select-all').addEventListener('click', toggleAllCheckboxes);
};

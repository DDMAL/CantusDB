window.addEventListener("load", function () {
    // check the correct radio button according to the GET parameter
    const anyChoice = document.getElementById("anyChoice");
    const massChoice = document.getElementById("massChoice");
    const officeChoice = document.getElementById("officeChoice");

    const urlParams = new URLSearchParams(window.location.search);
    const massOffice = urlParams.get("mass_office");

    switch (massOffice) {
        case "Mass":
            massChoice.checked = true;
            break;
        case "Office":
            officeChoice.checked = true;
            break;
        default:
            anyChoice.checked = true;
    }
});

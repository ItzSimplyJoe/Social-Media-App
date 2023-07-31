document.addEventListener('click', function (event) {
    const dropdownToggle = event.target.closest('.dropdown-toggle');
    if (dropdownToggle) {
      const dropdownMenu = dropdownToggle.nextElementSibling;
      if (dropdownMenu) {
        dropdownMenu.classList.toggle('show');
      }
    } else {
      const dropdownMenus = document.querySelectorAll('.dropdown-menu');
      dropdownMenus.forEach((menu) => {
        menu.classList.remove('show');
      });
    }
  });
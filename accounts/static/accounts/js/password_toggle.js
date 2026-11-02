/**
 * MECHORA Password Visibility Toggle
 * Provides safe show/hide toggling for password input fields without leaking credentials.
 */
document.addEventListener("DOMContentLoaded", function () {
    function initPasswordToggles() {
        const toggleButtons = document.querySelectorAll(".mechora-password-toggle-btn");

        toggleButtons.forEach(function (btn) {
            if (btn.dataset.initialized) return;
            btn.dataset.initialized = "true";

            btn.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();

                const wrapper = btn.closest(".mechora-password-wrapper");
                if (!wrapper) return;

                const input = wrapper.querySelector("input");
                const icon = btn.querySelector(".material-symbols-outlined");
                if (!input) return;

                const isCurrentlyPassword = input.type === "password";
                input.type = isCurrentlyPassword ? "text" : "password";

                if (icon) {
                    icon.textContent = isCurrentlyPassword ? "visibility_off" : "visibility";
                }

                btn.setAttribute(
                    "title",
                    isCurrentlyPassword ? "Hide password" : "Show password"
                );
                btn.setAttribute(
                    "aria-label",
                    isCurrentlyPassword ? "Hide password" : "Show password"
                );
            });
        });
    }

    initPasswordToggles();

    // Re-initialize if elements are dynamically inserted or re-rendered
    const observer = new MutationObserver(function () {
        initPasswordToggles();
    });

    observer.observe(document.body, { childList: true, subtree: true });
});

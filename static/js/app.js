// MukoLend Main JavaScript Helpers

document.addEventListener('DOMContentLoaded', function () {
    // 1. Mobile Hamburger Menu Toggle
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    if (mobileBtn && mobileMenu) {
        mobileBtn.addEventListener('click', function () {
            mobileMenu.classList.toggle('hidden');
        });
    }

    // Prevent accidental repeated submissions of loan and repayment forms.
    document.querySelectorAll('form[data-disable-on-submit]').forEach(form => {
        form.addEventListener('submit', function (event) {
            if (this.dataset.submitting === 'true') {
                event.preventDefault();
                return;
            }
            this.dataset.submitting = 'true';
            const submitButton = this.querySelector('button[type="submit"]');
            if (submitButton) submitButton.disabled = true;
        });
    });

    // 2. Lucide Icons Initializer
    if (window.lucide) {
        lucide.createIcons();
    }

    // 3. One-Click Copy Helper for Invite Codes
    document.querySelectorAll('.copy-invite-btn').forEach(button => {
        button.addEventListener('click', function () {
            const code = this.getAttribute('data-code');
            if (!code) return;

            navigator.clipboard.writeText(code).then(() => {
                const originalHtml = this.innerHTML;
                this.innerHTML = '<span class="text-xs font-bold text-emerald-600 flex items-center gap-1">✓ Copied!</span>';
                setTimeout(() => {
                    this.innerHTML = originalHtml;
                    if (window.lucide) lucide.createIcons();
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy code: ', err);
            });
        });
    });

    // 4. Quick Amount Fillers for Repayment Form
    const amountInput = document.getElementById('repayAmountInput');
    if (amountInput) {
        document.querySelectorAll('.quick-pay-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                const val = this.getAttribute('data-amount');
                if (val) {
                    amountInput.value = parseFloat(val).toFixed(2);
                }
            });
        });
    }
});

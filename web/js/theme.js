/* ==========================================================================
   COGNIHIRE - Dynamic Theming (theme.js)
   ========================================================================== */

function applyTheme(roleCategory) {
    // Reset existing themes
    document.documentElement.removeAttribute('data-theme');
    
    const roleLower = roleCategory.toLowerCase();
    
    if (roleLower.includes('finance') || roleLower.includes('bank')) {
        document.documentElement.setAttribute('data-theme', 'finance');
    } else if (roleLower.includes('government') || roleLower.includes('ias')) {
        document.documentElement.setAttribute('data-theme', 'government');
    } else {
        // Default to technical/software theme
        document.documentElement.setAttribute('data-theme', 'tech');
    }
}

function toggleMonoTheme() {
    const isDark = document.documentElement.toggleAttribute('data-dark');
    localStorage.setItem('cognihire-dark', isDark);
}

if (localStorage.getItem('cognihire-dark') === 'true') document.documentElement.setAttribute('data-dark', '');

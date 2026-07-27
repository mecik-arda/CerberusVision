(() => {
    const savedTheme = localStorage.getItem('cerberus-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.classList.toggle('dark', savedTheme ? savedTheme === 'dark' : prefersDark);
})();

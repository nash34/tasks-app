let inactivityTimer;
function resetTimer() {
    clearTimeout(inactivityTimer);
    inactivityTimer = setTimeout(() => {
        window.location.href = '/logout';
    }, 5 * 60 * 1000);  // 5 minutes
}
document.addEventListener('mousemove', resetTimer);
document.addEventListener('keydown', resetTimer);
document.addEventListener('touchstart', resetTimer);
resetTimer();
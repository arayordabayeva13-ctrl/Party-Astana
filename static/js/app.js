// Navbar scroll shadow
const nav = document.getElementById('mainNav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 20);
  }, { passive: true });
}

// Radio reg-type cards keyboard accessibility
document.querySelectorAll('.reg-type-radio').forEach(radio => {
  const lbl = radio.nextElementSibling;
  if (lbl) {
    lbl.setAttribute('tabindex', '0');
    lbl.addEventListener('keydown', e => {
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); radio.click(); }
    });
  }
});

// Auto-dismiss alerts
setTimeout(() => {
  document.querySelectorAll('.alert-dismissible').forEach(el => {
    el.style.transition = 'opacity .5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  });
}, 4000);

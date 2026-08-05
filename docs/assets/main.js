// Navigation toggle for mobile devices
document.addEventListener('DOMContentLoaded', function() {
    const navToggle = document.querySelector('.nav__toggle');
    const navMenu = document.querySelector('.nav__menu');
    const navLinks = document.querySelectorAll('.nav__link');
    
    if (navToggle && navMenu) {
        // Toggle menu
        navToggle.addEventListener('click', function() {
            const isOpen = navMenu.classList.contains('is-open');
            navMenu.classList.toggle('is-open');
            navToggle.setAttribute('aria-expanded', !isOpen);
            
            // Animate toggle bars
            const bars = navToggle.querySelectorAll('.nav__toggle-bar');
            if (!isOpen) {
                bars[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
                bars[1].style.opacity = '0';
                bars[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
            } else {
                bars[0].style.transform = 'none';
                bars[1].style.opacity = '1';
                bars[2].style.transform = 'none';
            }
        });
        
        // Close menu when clicking a link
        navLinks.forEach(function(link) {
            link.addEventListener('click', function() {
                navMenu.classList.remove('is-open');
                navToggle.setAttribute('aria-expanded', 'false');
                
                // Reset toggle bars
                const bars = navToggle.querySelectorAll('.nav__toggle-bar');
                bars[0].style.transform = 'none';
                bars[1].style.opacity = '1';
                bars[2].style.transform = 'none';
            });
        });
        
        // Close menu when clicking outside
        document.addEventListener('click', function(event) {
            if (!navToggle.contains(event.target) && !navMenu.contains(event.target)) {
                navMenu.classList.remove('is-open');
                navToggle.setAttribute('aria-expanded', 'false');
                
                // Reset toggle bars
                const bars = navToggle.querySelectorAll('.nav__toggle-bar');
                bars[0].style.transform = 'none';
                bars[1].style.opacity = '1';
                bars[2].style.transform = 'none';
            }
        });
    }
    
    // Smooth scroll for anchor links (fallback for browsers without CSS scroll-behavior)
    document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                e.preventDefault();
                const navHeight = document.querySelector('.nav').offsetHeight;
                const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset - navHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Add scroll-based navigation highlighting
    const sections = document.querySelectorAll('section[id]');
    const navLinksArray = Array.from(navLinks);
    
    function highlightNavLink() {
        const scrollPosition = window.scrollY + 100;
        
        sections.forEach(function(section) {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.offsetHeight;
            const sectionId = section.getAttribute('id');
            
            if (scrollPosition >= sectionTop && scrollPosition < sectionTop + sectionHeight) {
                navLinksArray.forEach(function(link) {
                    link.classList.remove('is-active');
                    if (link.getAttribute('href') === '#' + sectionId) {
                        link.classList.add('is-active');
                    }
                });
            }
        });
    }
    
    // Throttle scroll events for performance
    let ticking = false;
    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(function() {
                highlightNavLink();
                ticking = false;
            });
            ticking = true;
        }
    });
    
    // Initial highlight
    highlightNavLink();
});

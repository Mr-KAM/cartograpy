// Enhanced UI JavaScript for Cartograpy
document.addEventListener('DOMContentLoaded', function() {
    // Variables globales
    const navbar = document.querySelector('.navbar');
    const hamburger = document.getElementById('hamburger');
    const navMenu = document.getElementById('nav-menu');
    const navLinks = document.querySelectorAll('.nav-link');
    const dropdownItems = document.querySelectorAll('.nav-item');

    // Effet de scroll sur la navbar
    let lastScrollTop = 0;
    let scrollTimeout;

    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        // Ajouter classe scrolled
        if (scrollTop > 100) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }

        // Auto-hide navbar on scroll down (desktop only)
        if (window.innerWidth > 768) {
            clearTimeout(scrollTimeout);
            
            if (scrollTop > lastScrollTop && scrollTop > 200) {
                navbar.classList.add('hidden');
            } else {
                navbar.classList.remove('hidden');
            }
            
            // Show navbar when stopping scroll
            scrollTimeout = setTimeout(() => {
                navbar.classList.remove('hidden');
            }, 150);
        }
        
        lastScrollTop = scrollTop;
        updateReadingProgress();
    });

    // Progress bar de lecture
    function createReadingProgress() {
        const progressBar = document.createElement('div');
        progressBar.className = 'reading-progress';
        progressBar.style.cssText = `
            position: fixed;
            top: 80px;
            left: 0;
            width: 0%;
            height: 3px;
            background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
            z-index: 1000;
            transition: width 0.3s ease;
            border-radius: 0 2px 2px 0;
        `;
        document.body.appendChild(progressBar);
        return progressBar;
    }

    const progressBar = createReadingProgress();

    function updateReadingProgress() {
        const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = Math.min((window.scrollY / totalHeight) * 100, 100);
        progressBar.style.width = progress + '%';
    }

    // Bouton scroll to top
    function createScrollToTopButton() {
        const scrollToTopBtn = document.createElement('button');
        scrollToTopBtn.className = 'scroll-to-top';
        scrollToTopBtn.innerHTML = '↑';
        scrollToTopBtn.title = 'Retour en haut';
        scrollToTopBtn.style.cssText = `
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: var(--primary-color);
            color: white;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            border: none;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: bold;
            transition: var(--transition);
            box-shadow: var(--shadow-lg);
            z-index: 1000;
        `;
        
        scrollToTopBtn.addEventListener('mouseenter', function() {
            this.style.background = 'var(--secondary-color)';
            this.style.transform = 'translateY(-3px) scale(1.1)';
        });
        
        scrollToTopBtn.addEventListener('mouseleave', function() {
            this.style.background = 'var(--primary-color)';
            this.style.transform = 'translateY(0) scale(1)';
        });
        
        document.body.appendChild(scrollToTopBtn);
        return scrollToTopBtn;
    }

    const scrollToTopBtn = createScrollToTopButton();

    window.addEventListener('scroll', function() {
        if (window.scrollY > 300) {
            scrollToTopBtn.style.display = 'flex';
            setTimeout(() => {
                scrollToTopBtn.style.opacity = '1';
                scrollToTopBtn.style.transform = 'translateY(0) scale(1)';
            }, 10);
        } else {
            scrollToTopBtn.style.opacity = '0';
            scrollToTopBtn.style.transform = 'translateY(10px) scale(0.9)';
            setTimeout(() => {
                if (window.scrollY <= 300) {
                    scrollToTopBtn.style.display = 'none';
                }
            }, 300);
        }
    });

    scrollToTopBtn.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    // Gestion du menu hamburger
    if (hamburger && navMenu) {
        hamburger.addEventListener('click', function() {
            hamburger.classList.toggle('active');
            navMenu.classList.toggle('active');
            
            // Prévenir le scroll du body quand le menu est ouvert
            if (navMenu.classList.contains('active')) {
                document.body.style.overflow = 'hidden';
            } else {
                document.body.style.overflow = '';
            }
        });
    }

    // Fermeture du menu mobile
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            if (hamburger && navMenu) {
                hamburger.classList.remove('active');
                navMenu.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });

    // Gestion des dropdowns sur mobile
    dropdownItems.forEach(item => {
        const link = item.querySelector('.nav-link');
        const dropdown = item.querySelector('.dropdown');

        if (dropdown && link) {
            link.addEventListener('click', function(e) {
                if (window.innerWidth <= 768) {
                    e.preventDefault();
                    
                    // Fermer les autres dropdowns
                    dropdownItems.forEach(otherItem => {
                        if (otherItem !== item) {
                            otherItem.classList.remove('dropdown-open');
                        }
                    });
                    
                    item.classList.toggle('dropdown-open');
                }
            });
        }
    });

    // Smooth scrolling pour les liens internes
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const offsetTop = target.offsetTop - 100;
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
                
                // Fermer le menu mobile si ouvert
                if (hamburger && navMenu && navMenu.classList.contains('active')) {
                    hamburger.classList.remove('active');
                    navMenu.classList.remove('active');
                    document.body.style.overflow = '';
                }
            }
        });
    });

    // Highlighting des liens actifs avec Intersection Observer
    const observerOptions = {
        rootMargin: '-100px 0px -60% 0px',
        threshold: 0.1
    };

    const sectionObserver = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');
                if (id) {
                    // Remove active class from all links
                    document.querySelectorAll('.nav-link').forEach(link => {
                        link.classList.remove('active');
                    });
                    
                    // Add active class to current link
                    const activeLink = document.querySelector(`a[href="#${id}"]`);
                    if (activeLink) {
                        activeLink.classList.add('active');
                    }
                }
            }
        });
    }, observerOptions);

    // Observer toutes les sections avec un ID
    document.querySelectorAll('section[id], [id^="presentation"], [id^="fonctionnalites"], [id^="installation"], [id^="utilisation"]').forEach(section => {
        sectionObserver.observe(section);
    });

    // Animation d'apparition des éléments
    const animateElements = document.querySelectorAll('h1, h2, h3, .callout-note, .callout-tip, .callout-warning, .callout-important, .figure, .table, .sourceCode');
    
    const animationObserver = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '0';
                entry.target.style.transform = 'translateY(30px)';
                entry.target.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
                
                setTimeout(() => {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, entry.target.tagName === 'H1' ? 0 : Math.random() * 200);
                
                animationObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    animateElements.forEach(el => {
        animationObserver.observe(el);
    });

    // Fermeture du menu mobile lors du clic à l'extérieur
    document.addEventListener('click', function(e) {
        if (hamburger && navMenu && 
            !hamburger.contains(e.target) && 
            !navMenu.contains(e.target) &&
            navMenu.classList.contains('active')) {
            hamburger.classList.remove('active');
            navMenu.classList.remove('active');
            document.body.style.overflow = '';
        }
    });

    // Gestion du redimensionnement de la fenêtre
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            if (hamburger && navMenu) {
                hamburger.classList.remove('active');
                navMenu.classList.remove('active');
            }
            document.body.style.overflow = '';
            
            dropdownItems.forEach(item => {
                item.classList.remove('dropdown-open');
            });
        }
    });

    // Amélioration de l'accessibilité
    document.addEventListener('keydown', function(e) {
        // Fermer le menu mobile avec Escape
        if (e.key === 'Escape' && navMenu && navMenu.classList.contains('active')) {
            hamburger.classList.remove('active');
            navMenu.classList.remove('active');
            document.body.style.overflow = '';
        }
    });

    // Lazy loading amélioré pour les images
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver(function(entries) {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    
                    // Effet de fade-in
                    img.style.opacity = '0';
                    img.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                    
                    // Simuler le chargement
                    img.onload = function() {
                        img.style.opacity = '1';
                    };
                    
                    // Si l'image est déjà chargée
                    if (img.complete) {
                        img.style.opacity = '1';
                    }
                    
                    imageObserver.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img').forEach(img => {
            imageObserver.observe(img);
        });
    }

    // Initialize line numbering for code blocks (eviter la duplication)
    document.querySelectorAll('.sourceCode pre code').forEach(codeElement => {
        // Vérifier si la numérotation n'a pas déjà été appliquée
        if (!codeElement.querySelector('.code-line')) {
            const lines = codeElement.innerHTML.split('\n');
            if (lines.length > 1) {
                codeElement.innerHTML = lines.map((line, index) => {
                    if (index === lines.length - 1 && line.trim() === '') return '';
                    return `<span class="code-line" data-line="${index + 1}">${line}</span>`;
                }).filter(line => line !== '').join('\n');
            }
        }
    });

    // Amélioration des boutons de copie de code (eviter la duplication)
    function addCopyButtons() {
        document.querySelectorAll('.sourceCode').forEach(codeBlock => {
            // Vérifier si un bouton n'existe pas déjà
            if (!codeBlock.querySelector('.code-copy-button')) {
                const button = document.createElement('button');
                button.className = 'code-copy-button';
                button.innerHTML = 'Copier';
                button.title = 'Copier le code';
                
                button.addEventListener('click', async function() {
                    try {
                        const codeText = codeBlock.querySelector('pre code').textContent;
                        await navigator.clipboard.writeText(codeText);
                        
                        // Animation de succès
                        this.classList.add('copied');
                        this.innerHTML = 'Copié !';
                        this.style.transform = 'scale(1.1)';
                        
                        setTimeout(() => {
                            this.classList.remove('copied');
                            this.innerHTML = 'Copier';
                            this.style.transform = 'scale(1)';
                        }, 2000);
                    } catch (err) {
                        console.error('Erreur lors de la copie:', err);
                    }
                });
                
                codeBlock.appendChild(button);
            }
        });
    }

    // Call the function to add copy buttons
    addCopyButtons();

    // Amélioration des code blocks avec détection de langage
    document.querySelectorAll('.sourceCode').forEach(codeBlock => {
        // Détecter le langage depuis les classes
        const classes = codeBlock.className;
        let language = '';
        
        if (classes.includes('python')) language = 'python';
        else if (classes.includes('javascript') || classes.includes('js')) language = 'javascript';
        else if (classes.includes('bash') || classes.includes('shell')) language = 'bash';
        else if (classes.includes('json')) language = 'json';
        else if (classes.includes('html')) language = 'html';
        else if (classes.includes('css')) language = 'css';
        
        if (language) {
            codeBlock.setAttribute('data-lang', language);
        }
        
        // Ajouter des effects d'interaction
        codeBlock.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 12px 40px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2)';
        });
        
        codeBlock.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1)';
        });
    });

    // Highlighting syntax amélioré pour les éléments code
    document.querySelectorAll('code:not(pre code)').forEach(code => {
        const text = code.textContent;
        
        // Ajouter des effets pour le code inline
        code.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.05)';
            this.style.boxShadow = '0 4px 12px rgba(16, 185, 129, 0.3)';
        });
        
        code.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
            this.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1)';
        });
    });

    // Initialisation des animations
    updateReadingProgress();
    
    console.log('Enhanced UI initialized successfully for Cartograpy! 🗺️');
});

// Fonction utilitaire pour le débounce
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Performance optimizations
const debouncedResize = debounce(() => {
    // Recalculer les dimensions si nécessaire
}, 250);

window.addEventListener('resize', debouncedResize);

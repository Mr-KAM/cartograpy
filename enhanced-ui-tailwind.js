// Enhanced UI interactions with Tailwind CSS

class CartograpyUI {
  constructor() {
    this.init();
  }

  init() {
    this.setupScrollEffects();
    this.setupAnimations();
    this.setupInteractions();
    this.setupParticles();
  }

  setupScrollEffects() {
    // Intersection Observer for scroll animations
    const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-fade-in-up');
        }
      });
    }, observerOptions);

    // Observe all feature cards and sections
    document.querySelectorAll('.group, section').forEach(el => {
      observer.observe(el);
    });

    // Parallax effect for floating elements
    window.addEventListener('scroll', () => {
      const scrolled = window.pageYOffset;
      const rate = scrolled * -0.5;
      
      document.querySelectorAll('.floating').forEach(el => {
        el.style.transform = `translateY(${rate}px)`;
      });
    });
  }

  setupAnimations() {
    // Stagger animations for feature cards
    const featureCards = document.querySelectorAll('.group');
    featureCards.forEach((card, index) => {
      card.style.animationDelay = `${index * 0.1}s`;
    });

    // Typing animation for code examples
    this.typeWriter();
  }

  setupInteractions() {
    // Enhanced hover effects for cards
    document.querySelectorAll('.group').forEach(card => {
      card.addEventListener('mouseenter', () => {
        this.addGlowEffect(card);
      });

      card.addEventListener('mouseleave', () => {
        this.removeGlowEffect(card);
      });
    });

    // Copy to clipboard with feedback
    this.setupCopyFunctionality();

    // Mobile menu toggle
    this.setupMobileMenu();
  }

  setupParticles() {
    // Create floating particles in the hero section
    const heroSection = document.querySelector('section');
    if (heroSection) {
      for (let i = 0; i < 20; i++) {
        this.createParticle(heroSection);
      }
    }
  }

  createParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'absolute w-1 h-1 bg-blue-500/30 rounded-full pointer-events-none';
    
    // Random position
    particle.style.left = Math.random() * 100 + '%';
    particle.style.top = Math.random() * 100 + '%';
    
    // Random animation duration
    particle.style.animationDuration = (3 + Math.random() * 4) + 's';
    particle.style.animationDelay = Math.random() * 2 + 's';
    
    particle.classList.add('animate-float');
    
    container.appendChild(particle);

    // Remove and recreate after animation
    setTimeout(() => {
      if (particle.parentNode) {
        particle.parentNode.removeChild(particle);
        this.createParticle(container);
      }
    }, 7000);
  }

  addGlowEffect(element) {
    element.style.filter = 'drop-shadow(0 0 20px rgba(59, 130, 246, 0.3))';
    element.style.transform = 'translateY(-8px) scale(1.02)';
  }

  removeGlowEffect(element) {
    element.style.filter = '';
    element.style.transform = '';
  }

  typeWriter() {
    const codeElements = document.querySelectorAll('.typing-effect');
    
    codeElements.forEach(element => {
      const text = element.textContent;
      element.textContent = '';
      
      let i = 0;
      const timer = setInterval(() => {
        if (i < text.length) {
          element.textContent += text.charAt(i);
          i++;
        } else {
          clearInterval(timer);
        }
      }, 50);
    });
  }

  setupCopyFunctionality() {
    document.querySelectorAll('[data-copy]').forEach(button => {
      button.addEventListener('click', async (e) => {
        const textToCopy = button.getAttribute('data-copy');
        
        try {
          await navigator.clipboard.writeText(textToCopy);
          this.showCopyFeedback(button);
        } catch (err) {
          console.error('Failed to copy: ', err);
        }
      });
    });
  }

  showCopyFeedback(button) {
    const originalIcon = button.innerHTML;
    button.innerHTML = `
      <svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
      </svg>
    `;
    
    setTimeout(() => {
      button.innerHTML = originalIcon;
    }, 2000);
  }

  setupMobileMenu() {
    const mobileMenuButton = document.querySelector('[data-mobile-menu]');
    const mobileMenu = document.querySelector('[data-mobile-menu-content]');
    
    if (mobileMenuButton && mobileMenu) {
      mobileMenuButton.addEventListener('click', () => {
        mobileMenu.classList.toggle('hidden');
        mobileMenu.classList.toggle('animate-fade-in-down');
      });
    }
  }

  // Utility functions for smooth animations
  static easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1;
  }

  static lerp(start, end, factor) {
    return start + (end - start) * factor;
  }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new CartograpyUI();
});

// Add custom Tailwind utilities via JavaScript
document.addEventListener('DOMContentLoaded', () => {
  // Add custom CSS for advanced effects
  const style = document.createElement('style');
  style.textContent = `
    @keyframes float {
      0%, 100% { 
        transform: translateY(0px) rotate(0deg); 
      }
      33% { 
        transform: translateY(-10px) rotate(1deg); 
      }
      66% { 
        transform: translateY(5px) rotate(-1deg); 
      }
    }
    
    @keyframes pulse-glow {
      0%, 100% {
        box-shadow: 0 0 5px rgba(59, 130, 246, 0.5);
      }
      50% {
        box-shadow: 0 0 20px rgba(59, 130, 246, 0.8), 0 0 30px rgba(139, 92, 246, 0.6);
      }
    }
    
    .animate-pulse-glow {
      animation: pulse-glow 2s ease-in-out infinite;
    }
    
    .text-shadow {
      text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
    }
    
    /* Custom scrollbar for webkit browsers */
    .custom-scrollbar::-webkit-scrollbar {
      width: 6px;
    }
    
    .custom-scrollbar::-webkit-scrollbar-track {
      background: #1e293b;
    }
    
    .custom-scrollbar::-webkit-scrollbar-thumb {
      background: #475569;
      border-radius: 3px;
    }
    
    .custom-scrollbar::-webkit-scrollbar-thumb:hover {
      background: #64748b;
    }
    
    /* Gradient border animation */
    @keyframes gradient-border {
      0% { border-image-source: linear-gradient(45deg, #3b82f6, #8b5cf6); }
      25% { border-image-source: linear-gradient(45deg, #8b5cf6, #06b6d4); }
      50% { border-image-source: linear-gradient(45deg, #06b6d4, #10b981); }
      75% { border-image-source: linear-gradient(45deg, #10b981, #f59e0b); }
      100% { border-image-source: linear-gradient(45deg, #f59e0b, #3b82f6); }
    }
    
    .animate-gradient-border {
      border-width: 2px;
      border-style: solid;
      border-image: linear-gradient(45deg, #3b82f6, #8b5cf6) 1;
      animation: gradient-border 3s ease-in-out infinite;
    }
  `;
  document.head.appendChild(style);
});

// Copy to clipboard functionality
window.copyToClipboard = async function(text) {
  try {
    await navigator.clipboard.writeText(text);
    
    // Show toast notification
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in-up';
    toast.textContent = 'Copié dans le presse-papiers !';
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.classList.add('animate-fade-out');
      setTimeout(() => {
        document.body.removeChild(toast);
      }, 300);
    }, 2000);
  } catch (err) {
    console.error('Erreur lors de la copie:', err);
  }
};

// Smooth scroll with offset for fixed navbar
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      const offset = 80; // Height of fixed navbar
      const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - offset;
      
      window.scrollTo({
        top: targetPosition,
        behavior: 'smooth'
      });
    }
  });
});

export default CartograpyUI;

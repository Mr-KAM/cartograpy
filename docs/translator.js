/**
 * Google Translate Floating Action Button (FAB)
 * Enhances Google Translate integration with a user-friendly floating button.
 *
 * Usage:
 * 1. Include the Google Translate API script in your HTML:
 * <script type="text/javascript" src="//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>
 * 2. Add the required HTML elements to your body:
 * <div class="translate-container">
 * <button id="translateBtn" class="translate-btn" aria-label="Translate Page">
 * <span class="translate-icon">🌐</span>
 * <span class="translate-text">Traduction</span>
 * </button>
 * <div id="google_translate_element" class="google-translate-widget"></div>
 * </div>
 * 3. Include this JavaScript file.
 */

// Configuration des langues supportées
const SUPPORTED_LANGUAGES = 'en,es,de,it,pt,ar,zh,ja,ko,ru,hi,tr,nl,sv,da,no,fi,pl,cs,hu,ro,bg,hr,sk,sl,et,lv,lt,mt,el,cy,ga,eu,ca,gl,is,mk,sq,sr,bs,me,uk,be,kk,ky,uz,tg,mn,my,th,vi,id,ms,tl,sw,yo,ig,ha,zu,xh,af,st,tn,nso,ve,ts,ss,nr,rw,ny,sn,lg,ak,tw,gn,ay,qu,ht,la,eo,jw,su,mi,sm,to,fj,haw,mg,co,fy,lb,ga,gd,br,kw,an,ia,vo,ks,ne,si,ta,te,kn,ml,bn,as,or,gu,pa,ur,fa,ps,sd,dv,bo,ug,am,ti,om,so,rn';

/**
 * Initialise le widget Google Translate.
 * Cette fonction est appelée automatiquement par l'API Google Translate.
 * Elle configure les options d'affichage du widget.
 */
function googleTranslateElementInit() {
    try {
        new google.translate.TranslateElement({
            pageLanguage: 'fr', // Langue par défaut de votre site (à adapter si nécessaire)
            includedLanguages: SUPPORTED_LANGUAGES,
            layout: google.translate.TranslateElement.InlineLayout.SIMPLE,
            autoDisplay: false, // Important pour contrôler l'affichage avec le FAB
            multilanguagePage: true
        }, 'google_translate_element');

        console.log('✅ Google Translate widget initialized successfully.');
    } catch (error) {
        console.error('❌ Error initializing Google Translate widget:', error);
    }
}

/**
 * Classe pour gérer le bouton flottant de traduction (FAB) et son interaction avec le widget Google Translate.
 */
class GoogleTranslateFAB {
    constructor() {
        /** @type {HTMLElement | null} */
        this.translateBtn = null;
        /** @type {HTMLElement | null} */
        this.translateElement = null;
        /** @type {boolean} */
        this.isVisible = false;
        /** @type {number | null} */
        this.pulseTimeout = null;
        /** @type {number | null} */
        this.removePulseTimeout = null;
        /** @type {MutationObserver | null} */
        this.languageChangeObserver = null;

        this.init();
    }

    /**
     * Initialise le bouton flottant et configure les écouteurs d'événements.
     * Attend que le DOM soit complètement chargé avant de configurer les éléments.
     */
    init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', this.setupElements.bind(this));
        } else {
            this.setupElements();
        }
    }

    /**
     * Récupère les éléments DOM nécessaires et ajoute les styles personnalisés.
     * Affiche un message d'erreur si les éléments requis ne sont pas trouvés.
     */
    setupElements() {
        this.translateBtn = document.getElementById('translateBtn');
        this.translateElement = document.getElementById('google_translate_element');

        if (!this.translateBtn || !this.translateElement) {
            console.error('❌ Translation FAB elements not found in the DOM. Make sure #translateBtn and #google_translate_element exist.');
            return;
        }

        this.addCustomStyles();
        this.setupEventListeners();
        console.log('✅ Google Translate FAB configured.');
    }

    /**
     * Configure tous les écouteurs d'événements pour le bouton FAB et le document.
     */
    setupEventListeners() {
        // Toggle the translation widget on button click
        this.translateBtn.addEventListener('click', this.handleButtonClick.bind(this));

        // Hide the widget when clicking outside
        document.addEventListener('click', this.handleDocumentClick.bind(this));

        // Hide the widget on Escape key press
        document.addEventListener('keydown', this.handleKeyDown.bind(this));

        // Handle window resizing (though less critical with current CSS)
        window.addEventListener('resize', this.adjustPosition.bind(this));

        // Set up detection for language changes within the Google Translate widget
        this.setupLanguageChangeDetection();
    }

    /**
     * Gère le clic sur le bouton de traduction.
     * @param {Event} e - L'événement de clic.
     */
    handleButtonClick(e) {
        e.stopPropagation(); // Empêche la propagation de l'événement au document
        this.toggleTranslateWidget();
    }

    /**
     * Gère les clics sur le document pour fermer le widget.
     * @param {Event} e - L'événement de clic.
     */
    handleDocumentClick(e) {
        if (this.isVisible &&
            !this.translateBtn.contains(e.target) &&
            !this.translateElement.contains(e.target)) {
            this.hideTranslateWidget();
        }
    }

    /**
     * Gère les pressions de touche pour fermer le widget avec 'Escape'.
     * @param {KeyboardEvent} e - L'événement clavier.
     */
    handleKeyDown(e) {
        if (e.key === 'Escape' && this.isVisible) {
            this.hideTranslateWidget();
        }
    }

    /**
     * Ajoute les styles CSS personnalisés dynamiquement au document.
     * Cela assure que les styles sont toujours présents et peuvent être facilement modifiés ici.
     */
    addCustomStyles() {
        const styleId = 'translate-fab-styles';
        if (document.getElementById(styleId)) {
            return; // Styles already added
        }

        const styles = `
            /* Styles for the Floating Action Button (FAB) container */
            .translate-container {
                position: fixed;
                bottom: 40px;
                right: 20px;
                z-index: 1000;
            }

            /* Styles for the FAB itself */
            .translate-btn {
                background: rgba(0, 0, 0, 0.8) !important;
                color: white;
                border: none;
                padding: 12px 16px;
                border-radius: 50px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 0.9rem;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                transition: all 0.3s ease;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                min-width: 60px;
                justify-content: center;
            }

            .translate-btn:hover {
                background: rgba(0, 0, 0, 0.9) !important;
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.4);
            }

            .translate-btn:active {
                transform: translateY(0);
            }

            .translate-icon {
                font-size: 1.2rem;
                line-height: 1;
            }

            /* Styles for the Google Translate widget container */
            #google_translate_element {
                position: absolute;
                bottom: 100%; /* Position above the FAB */
                right: 0;
                margin-bottom: 0px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.2);
                padding: 15px;
                opacity: 0;
                visibility: hidden;
                transform: translateY(10px) scale(0.95);
                transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55); /* More engaging animation */
                min-width: 200px;
                max-width: 300px;
            }

            #google_translate_element.show {
                opacity: 1;
                visibility: visible;
                transform: translateY(0) scale(1);
            }

            /* Full customization of the Google Translate language selector */
            .goog-te-combo {
                background: #f8f9fa !important;
                border: 2px solid #e9ecef !important;
                border-radius: 8px !important;
                padding: 10px 12px !important;
                width: 100% !important;
                font-size: 0.9rem !important;
                font-family: inherit !important;
                cursor: pointer !important;
                transition: all 0.3s ease !important;
                outline: none !important;
                box-sizing: border-box; /* Ensures padding doesn't affect overall width */
            }

            .goog-te-combo:hover {
                border-color: #667eea !important;
                background: #ffffff !important;
            }

            .goog-te-combo:focus {
                border-color: #667eea !important;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
                background: #ffffff !important;
            }

            /* Hide the default Google Translate top bar */
            .goog-te-banner-frame {
                display: none !important;
            }

            body {
                top: 0 !important; /* Resets body top padding added by Google Translate */
            }

            .goog-te-menu-value {
                color: #333 !important;
            }

            .goog-te-gadget {
                font-family: inherit !important;
            }

            .goog-te-gadget-simple {
                background: transparent !important;
                border: none !important;
                font-size: inherit !important;
            }

            /* Responsive adjustments for mobile screens */
            @media screen and (max-width: 768px) {
                .translate-container {
                    bottom: 15px;
                    right: 15px;
                }

                .translate-text {
                    display: none; /* Hide text on smaller screens, show only icon */
                }

                .translate-btn {
                    width: 56px; /* Make FAB a perfect circle */
                    height: 56px;
                    padding: 0;
                    border-radius: 50%;
                }

                #google_translate_element {
                    right: 0; /* Align widget to the right on mobile */
                    min-width: unset; /* Remove min-width to allow flexible sizing */
                    max-width: calc(100vw - 30px); /* Max width relative to viewport minus margins */
                    transform-origin: bottom right;
                    /* Adjust vertical position slightly on mobile if needed */
                    bottom: calc(100% + 15px); /* Adjusted to be just above the button, considering mobile bottom padding */
                    left: auto; /* Ensure it stays right-aligned */
                    right: 0;
                }
            }

            /* Pulse animation to draw attention to the FAB */
            @keyframes pulse {
                0% { box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
                50% { box-shadow: 0 4px 12px rgba(0,0,0,0.5), 0 0 0 10px rgba(0,0,0,0.1); }
                100% { box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
            }

            .translate-btn.pulse {
                animation: pulse 2s infinite;
            }

            /* Confirmation Toast */
            .language-change-toast {
                position: fixed;
                top: 20px;
                right: 20px;
                background: #28a745; /* Green for success */
                color: white;
                padding: 12px 20px;
                border-radius: 25px;
                font-size: 0.9rem;
                font-family: inherit;
                z-index: 1001;
                opacity: 0;
                transform: translateY(-20px);
                transition: all 0.3s ease;
                box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3);
            }
        `;

        const styleSheet = document.createElement('style');
        styleSheet.id = styleId;
        styleSheet.textContent = styles;
        document.head.appendChild(styleSheet);
    }

    /**
     * Bascule la visibilité du widget de traduction.
     */
    toggleTranslateWidget() {
        if (this.isVisible) {
            this.hideTranslateWidget();
        } else {
            this.showTranslateWidget();
        }
    }

    /**
     * Affiche le widget de traduction avec une animation.
     */
    showTranslateWidget() {
        if (this.translateElement) {
            this.translateElement.classList.add('show');
            this.isVisible = true;
            this.removePulseEffect(); // Remove pulse when widget is open
            console.log('📖 Google Translate widget opened.');
        }
    }

    /**
     * Masque le widget de traduction avec une animation.
     */
    hideTranslateWidget() {
        if (this.translateElement) {
            this.translateElement.classList.remove('show');
            this.isVisible = false;
            console.log('📕 Google Translate widget closed.');
        }
    }

    /**
     * Ajuste la position du widget ou du bouton si nécessaire, par exemple sur redimensionnement.
     * Actuellement, le CSS gère la plupart des ajustements, mais cette fonction peut être étendue.
     */
    adjustPosition() {
        // No specific JS adjustment needed for current CSS, but kept for future expansion.
        // For example, if the widget needed to be dynamically positioned based on screen real estate.
    }

    /**
     * Configure un observateur de mutations pour détecter le chargement du sélecteur de langue Google Translate
     * et attacher un écouteur 'change' pour fermer le widget après sélection.
     */
    setupLanguageChangeDetection() {
        // Disconnect existing observer to prevent duplicates if called multiple times
        if (this.languageChangeObserver) {
            this.languageChangeObserver.disconnect();
        }

        const targetNode = document.body;
        const config = { childList: true, subtree: true };

        this.languageChangeObserver = new MutationObserver((mutationsList, observer) => {
            for (const mutation of mutationsList) {
                if (mutation.type === 'childList') {
                    const selectElement = document.querySelector('.goog-te-combo');
                    // Check if the select element exists and a listener hasn't been added yet
                    if (selectElement && !selectElement.hasAttribute('data-listener-added')) {
                        selectElement.setAttribute('data-listener-added', 'true'); // Mark to prevent duplicate listeners
                        selectElement.addEventListener('change', () => {
                            console.log('🌐 Language changed by user.');
                            this.hideTranslateWidget(); // Close widget after language selection
                            this.showLanguageChangeConfirmation(); // Show a confirmation toast
                        });
                        // Once the select is found and listener added, we can stop observing
                        // unless there's a reason to re-observe (e.g., widget re-initialization).
                        // For now, we'll keep observing as the widget might be removed/re-added by Google's script.
                    }
                }
            }
        });

        this.languageChangeObserver.observe(targetNode, config);
    }

    /**
     * Affiche une confirmation visuelle temporaire (toast) du changement de langue.
     */
    showLanguageChangeConfirmation() {
        const existingToast = document.querySelector('.language-change-toast');
        if (existingToast) {
            existingToast.remove(); // Remove any existing toast to prevent stacking
        }

        const toast = document.createElement('div');
        toast.textContent = '✅ Langue changée !';
        toast.classList.add('language-change-toast'); // Use a class for consistency and styling

        document.body.appendChild(toast);

        // Animate appearance
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        }, 50); // Small delay for smooth transition

        // Animate disappearance and remove
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-20px)';
            toast.addEventListener('transitionend', () => toast.remove(), { once: true });
        }, 2000); // Display for 2 seconds
    }

    /**
     * Ajoute l'animation 'pulse' au bouton FAB pour attirer l'attention.
     */
    addPulseEffect() {
        if (this.translateBtn && !this.isVisible) { // Only add pulse if widget is not open
            this.translateBtn.classList.add('pulse');
        }
    }

    /**
     * Retire l'animation 'pulse' du bouton FAB.
     */
    removePulseEffect() {
        if (this.translateBtn) {
            this.translateBtn.classList.remove('pulse');
        }
    }
}

/**
 * Initialisation de la classe GoogleTranslateFAB.
 * Utilise un singleton pattern pour s'assurer qu'une seule instance est créée.
 * Applique des effets d'animation de pulsation pour attirer l'attention initialement.
 */
let translateFABInstance = null;

function initializeFABSingleton() {
    if (!translateFABInstance) {
        translateFABInstance = new GoogleTranslateFAB();

        // Add pulse effect after a delay to grab attention, then remove it
        translateFABInstance.pulseTimeout = setTimeout(() => {
            translateFABInstance.addPulseEffect();
            translateFABInstance.removePulseTimeout = setTimeout(() => {
                translateFABInstance.removePulseEffect();
            }, 10000); // Remove pulse after 10 seconds
        }, 3000); // Add pulse after 3 seconds
    }
}

// Ensure the FAB is initialized as soon as the DOM is ready.
// This handles cases where the script is loaded async or deferred.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeFABSingleton);
} else {
    initializeFABSingleton();
}

// Fallback initialization for robustness, especially if the script is loaded in unusual ways.
window.addEventListener('load', () => {
    setTimeout(initializeFABSingleton, 500); // Small delay to ensure all assets are loaded
});

// Export for potential external usage (e.g., testing or module systems)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GoogleTranslateFAB, googleTranslateElementInit };
}
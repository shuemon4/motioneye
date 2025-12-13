/**
 * Lightweight client-side i18n for MotionEye
 *
 * Design principles:
 * - English is the source language (no translation file needed)
 * - Translations loaded on-demand for non-English users
 * - Falls back to English if translation missing
 * - Zero CPU impact on the Pi - all processing on client
 *
 * Usage:
 *   i18n.init('de', function() {
 *       i18n.translatePage();
 *   });
 *
 *   // In JavaScript:
 *   var msg = i18n.t('Apply');  // Returns translated string
 */
(function(window) {
    'use strict';

    var translations = {};
    var currentLang = 'en';
    var loaded = false;
    var basePath = '';

    var i18n = {
        /**
         * Initialize i18n with user's language preference
         * @param {string} lang - Language code (e.g., 'de', 'fr', 'es')
         * @param {function} callback - Called when ready
         * @param {string} path - Base path for translation files (optional)
         */
        init: function(lang, callback, path) {
            currentLang = lang || 'en';
            basePath = path || (window.basePath || '');

            // Normalize basePath to end with /
            if (basePath && !basePath.endsWith('/')) {
                basePath += '/';
            }

            // English needs no translation file - it's the source language
            if (currentLang === 'en') {
                loaded = true;
                if (callback) callback();
                return;
            }

            // Load translation file for other languages
            var xhr = new XMLHttpRequest();
            var url = basePath + 'static/js/i18n/' + currentLang + '.json';

            xhr.open('GET', url, true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200) {
                        try {
                            translations = JSON.parse(xhr.responseText);
                        } catch (e) {
                            console.warn('i18n: Failed to parse translations for ' + currentLang);
                            translations = {};
                        }
                    } else {
                        console.warn('i18n: No translations found for ' + currentLang + ', using English');
                    }
                    loaded = true;
                    if (callback) callback();
                }
            };
            xhr.send();
        },

        /**
         * Translate a string
         * @param {string} key - English source string
         * @param {object} vars - Optional variables for interpolation {name: value}
         * @returns {string} Translated string or original if not found
         */
        t: function(key, vars) {
            var result;

            if (currentLang === 'en' || !translations[key]) {
                result = key;
            } else {
                result = translations[key];
            }

            // Simple variable interpolation: "Hello {name}" + {name: "World"} = "Hello World"
            if (vars) {
                for (var varName in vars) {
                    if (vars.hasOwnProperty(varName)) {
                        result = result.replace(new RegExp('\\{' + varName + '\\}', 'g'), vars[varName]);
                    }
                }
            }

            return result;
        },

        /**
         * Translate all elements with data-i18n attribute
         * Call this after page load and after dynamic content is added
         */
        translatePage: function() {
            if (currentLang === 'en') return; // No translation needed for English

            // Translate text content
            var elements = document.querySelectorAll('[data-i18n]');
            for (var i = 0; i < elements.length; i++) {
                var el = elements[i];
                var key = el.getAttribute('data-i18n');
                var translated = this.t(key);

                // Handle different element types
                if (el.tagName === 'INPUT') {
                    if (el.placeholder) {
                        el.placeholder = translated;
                    }
                    if (el.value && el.type === 'button') {
                        el.value = translated;
                    }
                } else if (el.tagName === 'OPTION') {
                    el.textContent = translated;
                } else if (el.tagName === 'OPTGROUP') {
                    el.label = translated;
                } else {
                    // For most elements, only translate if they have no child elements
                    // (to avoid overwriting complex nested content)
                    if (el.children.length === 0) {
                        el.textContent = translated;
                    }
                }
            }

            // Translate title attributes (tooltips/help text)
            var titled = document.querySelectorAll('[data-i18n-title]');
            for (var j = 0; j < titled.length; j++) {
                var tel = titled[j];
                tel.title = this.t(tel.getAttribute('data-i18n-title'));
            }

            // Translate placeholder attributes
            var placeholders = document.querySelectorAll('[data-i18n-placeholder]');
            for (var k = 0; k < placeholders.length; k++) {
                var pel = placeholders[k];
                pel.placeholder = this.t(pel.getAttribute('data-i18n-placeholder'));
            }
        },

        /**
         * Translate a specific container (useful after dynamic content insertion)
         * @param {HTMLElement} container - The container element to translate
         */
        translateElement: function(container) {
            if (currentLang === 'en' || !container) return;

            var elements = container.querySelectorAll('[data-i18n]');
            for (var i = 0; i < elements.length; i++) {
                var el = elements[i];
                var key = el.getAttribute('data-i18n');
                if (el.children.length === 0) {
                    el.textContent = this.t(key);
                }
            }

            var titled = container.querySelectorAll('[data-i18n-title]');
            for (var j = 0; j < titled.length; j++) {
                titled[j].title = this.t(titled[j].getAttribute('data-i18n-title'));
            }
        },

        /**
         * Get current language code
         * @returns {string} Current language code
         */
        getLanguage: function() {
            return currentLang;
        },

        /**
         * Check if translations are loaded and ready
         * @returns {boolean} True if ready
         */
        isReady: function() {
            return loaded;
        },

        /**
         * Get all loaded translations (for debugging)
         * @returns {object} Translation dictionary
         */
        getTranslations: function() {
            return translations;
        }
    };

    // Expose globally as motionEyeI18n (avoids conflict with legacy gettext.js)
    window.motionEyeI18n = i18n;

})(window);

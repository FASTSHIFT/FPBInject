/*========================================
  FPBInject Workbench - i18n Module
  
  Internationalization support using i18next
  ========================================*/

/* Global i18n state */
let i18nInitialized = false;

/**
 * Initialize i18next with the specified language
 * @param {string} language - Language code (en, zh-CN, zh-TW)
 */
async function initI18n(language = 'en') {
  if (typeof i18next === 'undefined') {
    console.warn('i18next not loaded, skipping i18n initialization');
    return false;
  }

  try {
    await i18next.init({
      lng: language,
      fallbackLng: 'en',
      debug: false,
      resources: window.i18nResources || {},
      interpolation: {
        escapeValue: false,
      },
    });

    i18nInitialized = true;
    translatePage();
    return true;
  } catch (e) {
    console.error('Failed to initialize i18n:', e);
    return false;
  }
}

/**
 * Translate all elements with data-i18n attribute
 */
function translatePage() {
  if (!i18nInitialized) return;

  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.getAttribute('data-i18n');
    if (!key) return;

    // Get interpolation options if present
    let options = {};
    const optionsAttr = el.getAttribute('data-i18n-options');
    if (optionsAttr) {
      try {
        options = JSON.parse(optionsAttr);
      } catch (e) {
        console.warn('Invalid data-i18n-options:', optionsAttr);
      }
    }

    // Handle attribute translations like [placeholder]key or [title]key
    if (key.startsWith('[')) {
      const match = key.match(/\[(\w+)\](.+)/);
      if (match) {
        const attr = match[1];
        const translationKey = match[2];
        const translated = i18next.t(translationKey, options);
        if (translated !== translationKey) {
          el.setAttribute(attr, translated);
        }
      }
    } else {
      // Handle multiple keys separated by ;
      const keys = key.split(';');
      keys.forEach((k) => {
        if (k.startsWith('[')) {
          const match = k.match(/\[(\w+)\](.+)/);
          if (match) {
            const attr = match[1];
            const translationKey = match[2];
            const translated = i18next.t(translationKey, options);
            if (translated !== translationKey) {
              el.setAttribute(attr, translated);
            }
          }
        } else {
          const translated = i18next.t(k, options);
          if (translated !== k) {
            el.textContent = translated;
          }
        }
      });
    }
  });

  // Translate config schema labels if schema is loaded
  translateConfigSchema();
}

/**
 * Translate config schema labels and tooltips
 */
function translateConfigSchema() {
  if (!i18nInitialized || typeof getConfigSchema !== 'function') return;

  const schema = getConfigSchema();
  if (!schema) return;

  // Re-render config panel headers with translated group labels
  document.querySelectorAll('.config-group-header').forEach((header) => {
    const group = header.getAttribute('data-group');
    if (group) {
      const key = `config.groups.${group}`;
      const translated = i18next.t(key);
      if (translated !== key) {
        header.textContent = translated;
      }
    }
  });

  // Re-render config item labels
  for (const item of schema.schema) {
    const elementId = keyToElementId(item.key);
    const labelEl = document.querySelector(`label[for="${elementId}"]`);
    if (labelEl) {
      const key = `config.labels.${item.key}`;
      const translated = i18next.t(key);
      if (translated !== key) {
        labelEl.textContent = translated;
      }
    }

    // Update tooltips
    const configItem = document
      .querySelector(`.config-item [id="${elementId}"]`)
      ?.closest('.config-item');
    if (configItem) {
      const tooltipKey = `tooltips.${item.key}`;
      const translatedTooltip = i18next.t(tooltipKey);
      if (translatedTooltip !== tooltipKey) {
        configItem.setAttribute('title', translatedTooltip);
      }
    }
  }
}

/**
 * Change the current language
 * @param {string} lng - Language code
 */
async function changeLanguage(lng) {
  if (!i18nInitialized) {
    await initI18n(lng);
    return;
  }

  try {
    await i18next.changeLanguage(lng);
    translatePage();

    // Save language preference to localStorage
    localStorage.setItem('fpbinject_ui_language', lng);
  } catch (e) {
    console.error('Failed to change language:', e);
  }
}

/**
 * Get translation for a key
 * @param {string} key - Translation key
 * @param {string|object} fallbackOrOptions - Fallback string or interpolation options
 * @param {object} options - Interpolation options (if fallback is provided)
 * @returns {string} Translated string or fallback/key if not found
 */
function t(key, fallbackOrOptions = {}, options = {}) {
  // Handle case where second param is a fallback string
  let fallback = key;
  let opts = {};

  if (typeof fallbackOrOptions === 'string') {
    fallback = fallbackOrOptions;
    opts = options;
  } else {
    opts = fallbackOrOptions;
  }

  if (!i18nInitialized) return fallback;

  const result = i18next.t(key, opts);
  // If i18next returns the key (not found), use fallback
  return result === key ? fallback : result;
}

/**
 * Get current language
 * @returns {string} Current language code
 */
function getCurrentLanguage() {
  if (!i18nInitialized) return 'en';
  return i18next.language;
}

/**
 * Check if i18n is initialized
 * @returns {boolean}
 */
function isI18nReady() {
  return i18nInitialized;
}

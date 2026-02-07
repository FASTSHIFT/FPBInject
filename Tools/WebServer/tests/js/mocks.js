/**
 * Browser Environment Mocks - Enhanced for better coverage
 */

const mockLocalStorage = {
  _store: {},
  getItem(key) {
    return this._store[key] || null;
  },
  setItem(key, value) {
    this._store[key] = String(value);
  },
  removeItem(key) {
    delete this._store[key];
  },
  clear() {
    this._store = {};
  },
};

const mockElements = {};

function createMockElement(id) {
  const el = {
    id,
    value: '',
    _textContent: '',
    _innerHTML: '',
    _children: [],
    className: '',
    tagName: 'DIV',
    title: '',
    checked: false,
    disabled: false,
    open: false,
    options: [],
    selectedIndex: 0,
    _eventListeners: {},
    _attributes: {},
    dataset: {},

    get textContent() {
      return this._textContent;
    },
    set textContent(v) {
      this._textContent = v;
      this._innerHTML = String(v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    },
    get innerHTML() {
      // If we have children, build innerHTML from them
      if (this._children.length > 0) {
        return this._children
          .map((c) => {
            if (c._innerHTML) return c._innerHTML;
            if (c.textContent) return c.textContent;
            return '';
          })
          .join('');
      }
      return this._innerHTML;
    },
    set innerHTML(v) {
      this._innerHTML = v;
      this._children = [];
    },
    get children() {
      return this._children;
    },

    style: {
      display: '',
      opacity: '',
      width: '',
      height: '',
      background: '',
      visibility: '',
      pointerEvents: '',
      flex: '',
      position: '',
    },

    offsetHeight: 300,
    offsetWidth: 200,

    classList: {
      _classes: new Set(),
      add(cls) {
        this._classes.add(cls);
      },
      remove(cls) {
        this._classes.delete(cls);
      },
      contains(cls) {
        return this._classes.has(cls);
      },
      toggle(cls, force) {
        if (force !== undefined) {
          force ? this._classes.add(cls) : this._classes.delete(cls);
        } else {
          this._classes.has(cls)
            ? this._classes.delete(cls)
            : this._classes.add(cls);
        }
        return this._classes.has(cls);
      },
    },

    addEventListener(event, handler) {
      if (!this._eventListeners[event]) this._eventListeners[event] = [];
      this._eventListeners[event].push(handler);
    },
    removeEventListener(event, handler) {
      if (this._eventListeners[event]) {
        this._eventListeners[event] = this._eventListeners[event].filter(
          (h) => h !== handler,
        );
      }
    },
    dispatchEvent(event) {
      const handlers = this._eventListeners[event.type] || [];
      handlers.forEach((h) => h(event));
    },

    appendChild(child) {
      this._children.push(child);
      return child;
    },
    removeChild(child) {
      const idx = this._children.indexOf(child);
      if (idx >= 0) this._children.splice(idx, 1);
      return child;
    },
    remove() {},
    insertBefore(newNode, refNode) {
      return newNode;
    },

    querySelectorAll(selector) {
      return [];
    },
    querySelector(selector) {
      return null;
    },
    getElementsByClassName(cls) {
      return [];
    },

    getAttribute(name) {
      return this._attributes[name] || null;
    },
    setAttribute(name, value) {
      this._attributes[name] = value;
    },
    removeAttribute(name) {
      delete this._attributes[name];
    },
    hasAttribute(name) {
      return name in this._attributes;
    },

    closest(selector) {
      // Simple implementation for .sidebar-section
      if (selector === '.sidebar-section') {
        if (this.classList._classes.has('sidebar-section')) {
          return this;
        }
      }
      return null;
    },
    focus() {},
    blur() {},
    click() {},
    scrollIntoView(options) {},

    getBoundingClientRect() {
      return {
        top: 0,
        left: 0,
        right: 100,
        bottom: 100,
        width: 100,
        height: 100,
      };
    },
  };
  return el;
}

// Fetch mock with configurable responses
let fetchCalls = [];
let fetchResponses = {};
let defaultFetchResponse = { success: true };

// Special default responses for specific endpoints
const endpointDefaults = {
  '/api/logs': { tool_next: 0, raw_next: 0 },
};

const mockFetch = async (url, options = {}) => {
  fetchCalls.push({ url, options });

  // Find matching response (exact match or pattern match)
  let response = fetchResponses[url];
  if (!response) {
    for (const pattern of Object.keys(fetchResponses)) {
      if (url.includes(pattern)) {
        response = fetchResponses[pattern];
        break;
      }
    }
  }

  // Check endpoint defaults if no specific response set
  if (!response) {
    for (const pattern of Object.keys(endpointDefaults)) {
      if (url.includes(pattern)) {
        response = endpointDefaults[pattern];
        break;
      }
    }
  }

  response = response || defaultFetchResponse;

  // Handle SSE streaming response
  if (response._stream) {
    return {
      ok: true,
      status: 200,
      headers: { get: () => 'text/event-stream' },
      body: {
        getReader: () => ({
          _index: 0,
          _data: response._stream,
          async read() {
            if (this._index >= this._data.length) return { done: true };
            const chunk = this._data[this._index++];
            return { done: false, value: new TextEncoder().encode(chunk) };
          },
        }),
      },
    };
  }

  return {
    ok: response._ok !== false,
    status: response._status || 200,
    headers: { get: (h) => (h === 'content-type' ? 'application/json' : null) },
    json: async () => response,
    text: async () => JSON.stringify(response),
    body: { getReader: () => ({ read: async () => ({ done: true }) }) },
  };
};

// Document event listeners storage
const documentEventListeners = {};

// Enhanced document mock
const mockDocument = {
  getElementById(id) {
    if (!mockElements[id]) {
      mockElements[id] = createMockElement(id);
      // Set tagName for details elements
      if (id.startsWith('details-')) {
        mockElements[id].tagName = 'DETAILS';
      }
    }
    return mockElements[id];
  },
  querySelectorAll(selector) {
    // Return elements matching common selectors
    if (selector.startsWith('.')) {
      const cls = selector.slice(1);
      return Object.values(mockElements).filter((el) =>
        el.classList._classes.has(cls),
      );
    }
    // Handle attribute selectors like details[id^="details-"]
    if (selector.includes('[id^="')) {
      const match = selector.match(/\[id\^="([^"]+)"\]/);
      if (match) {
        const prefix = match[1];
        const tagMatch = selector.match(/^(\w+)\[/);
        const tag = tagMatch ? tagMatch[1].toUpperCase() : null;
        return Object.values(mockElements).filter((el) => {
          const idMatches = el.id.startsWith(prefix);
          const tagMatches = !tag || el.tagName === tag;
          return idMatches && tagMatches;
        });
      }
    }
    // Handle attribute selectors like .sidebar-section[data-section-id="device"]
    if (selector.includes('[data-section-id=')) {
      const match = selector.match(/\[data-section-id="([^"]+)"\]/);
      if (match) {
        const sectionId = match[1];
        return Object.values(mockElements).filter((el) => {
          return el.dataset && el.dataset.sectionId === sectionId;
        });
      }
    }
    // Handle .slot-item[data-slot="N"] selector
    if (selector.includes('.slot-item[data-slot=')) {
      const match = selector.match(/\[data-slot="(\d+)"\]/);
      if (match) {
        const slotNum = match[1];
        return Object.values(mockElements).filter((el) => {
          return (
            el.classList._classes.has('slot-item') &&
            el.dataset &&
            el.dataset.slot === slotNum
          );
        });
      }
    }
    return [];
  },
  querySelector(selector) {
    // Handle .slot-item[data-slot="N"] selector directly
    if (selector.includes('.slot-item[data-slot=')) {
      const match = selector.match(/\[data-slot="(\d+)"\]/);
      if (match) {
        const slotNum = match[1];
        const found = Object.values(mockElements).find((el) => {
          return (
            el.classList._classes.has('slot-item') &&
            el.dataset &&
            el.dataset.slot === slotNum
          );
        });
        return found || null;
      }
    }
    // Handle class selectors like .editor-tabs-header
    if (selector.startsWith('.')) {
      const className = selector.slice(1);
      const found = Object.values(mockElements).find((el) => {
        return (
          el.classList &&
          el.classList._classes &&
          el.classList._classes.has(className)
        );
      });
      if (found) return found;
      // Auto-create common editor elements
      if (
        className === 'editor-tabs-header' ||
        className === 'editor-tabs-content'
      ) {
        const el = createMockElement(className);
        el.classList.add(className);
        mockElements[className] = el;
        return el;
      }
    }
    const all = this.querySelectorAll(selector);
    return all[0] || null;
  },
  createElement(tag) {
    const el = createMockElement(
      `_created_${tag}_${Date.now()}_${Math.random()}`,
    );
    el.tagName = tag.toUpperCase();
    return el;
  },
  createTextNode(text) {
    return { nodeType: 3, textContent: text };
  },
  addEventListener(event, handler) {
    if (!documentEventListeners[event]) documentEventListeners[event] = [];
    documentEventListeners[event].push(handler);
  },
  removeEventListener(event, handler) {
    if (documentEventListeners[event]) {
      documentEventListeners[event] = documentEventListeners[event].filter(
        (h) => h !== handler,
      );
    }
  },
  dispatchEvent(event) {
    const handlers = documentEventListeners[event.type] || [];
    handlers.forEach((h) => h(event));
  },
  documentElement: {
    _theme: 'dark',
    getAttribute(name) {
      return name === 'data-theme' ? this._theme : null;
    },
    setAttribute(name, value) {
      if (name === 'data-theme') this._theme = value;
    },
    style: {
      setProperty(name, value) {
        this[name] = value;
      },
    },
  },
  body: createMockElement('body'),
};

// Save original document methods for reset
const originalQuerySelector = mockDocument.querySelector.bind(mockDocument);
const originalQuerySelectorAll =
  mockDocument.querySelectorAll.bind(mockDocument);

// Terminal mock with recording
class MockTerminal {
  constructor(opts) {
    this.options = opts || {};
    this._writes = [];
    this._cleared = false;
  }
  open(container) {}
  loadAddon(addon) {}
  writeln(msg) {
    this._writes.push({ type: 'line', msg });
    this._lastWrite = msg;
  }
  write(msg) {
    this._writes.push({ type: 'raw', msg });
    this._lastWrite = msg;
  }
  clear() {
    this._cleared = true;
    this._writes = [];
  }
  getSelection() {
    return '';
  }
  attachCustomKeyEventHandler(fn) {
    this._keyHandler = fn;
  }
  onData(fn) {
    this._dataHandler = fn;
  }
  getWrites() {
    return this._writes;
  }
}

// FitAddon mock
class MockFitAddon {
  constructor() {
    this._fitted = false;
  }
  fit() {
    this._fitted = true;
  }
}

// Ace editor mock
function createMockAceEditor() {
  return {
    _value: '',
    _theme: '',
    _mode: '',
    _options: {},
    _resized: false,
    _destroyed: false,
    setTheme(t) {
      this._theme = t;
    },
    session: {
      setMode(m) {
        this._mode = m;
      },
    },
    setOptions(o) {
      this._options = o;
    },
    setValue(v, pos) {
      this._value = v;
    },
    getValue() {
      return this._value;
    },
    resize() {
      this._resized = true;
    },
    destroy() {
      this._destroyed = true;
    },
    focus() {},
    blur() {},
    getSession() {
      return this.session;
    },
  };
}

const browserGlobals = {
  localStorage: mockLocalStorage,
  document: mockDocument,
  window: null,
  navigator: { clipboard: { writeText: () => Promise.resolve() } },
  console,
  setTimeout: (fn, ms) => {
    fn();
    return 1;
  },
  clearTimeout: () => {},
  setInterval: (fn, ms) => {
    return 1;
  },
  clearInterval: () => {},
  Promise,
  Map,
  Set,
  Array,
  Object,
  JSON,
  Math,
  Date,
  RegExp,
  Error,
  parseInt,
  parseFloat,
  isNaN,
  isFinite,
  encodeURIComponent,
  decodeURIComponent,
  encodeURI,
  decodeURI,
  fetch: mockFetch,
  alert: () => {},
  confirm: () => true,
  prompt: () => '',
  requestAnimationFrame: (cb) => {
    cb();
    return 1;
  },
  cancelAnimationFrame: () => {},
  getComputedStyle: () => ({ getPropertyValue: () => '300px' }),
  Terminal: MockTerminal,
  FitAddon: { FitAddon: MockFitAddon },
  ace: { edit: () => createMockAceEditor() },
  hljs: { highlightElement: () => {} },
  TextEncoder:
    typeof TextEncoder !== 'undefined'
      ? TextEncoder
      : class {
          encode(s) {
            return Buffer.from(s);
          }
        },
  TextDecoder:
    typeof TextDecoder !== 'undefined'
      ? TextDecoder
      : class {
          decode(b) {
            return b.toString();
          }
        },
};

browserGlobals.window = {
  localStorage: browserGlobals.localStorage,
  document: browserGlobals.document,
  navigator: browserGlobals.navigator,
  fetch: browserGlobals.fetch,
  alert: browserGlobals.alert,
  confirm: browserGlobals.confirm,
  addEventListener: () => {},
  removeEventListener: () => {},
  innerHeight: 1000,
  innerWidth: 1200,
  FPBState: null,
  getComputedStyle: browserGlobals.getComputedStyle,
  // These will be populated when application code loads
  writeToOutput: null,
  writeToSerial: null,
  startLogPolling: null,
  stopLogPolling: null,
  fpbInfo: null,
  updateDisabledState: null,
  updateSlotUI: null,
  updateMemoryInfo: null,
  openDisassembly: null,
  startAutoInjectPolling: null,
  stopAutoInjectPolling: null,
  checkConnectionStatus: null,
  checkBackendHealth: null,
  startBackendHealthCheck: null,
  stopBackendHealthCheck: null,
  saveConfig: null,
  openFileBrowser: null,
  switchEditorTab: null,
  escapeHtml: null,
};

function resetMocks() {
  mockLocalStorage.clear();
  fetchCalls = [];
  fetchResponses = {};
  mockDocument.documentElement._theme = 'dark';
  Object.keys(mockElements).forEach((k) => delete mockElements[k]);
  // Clear document event listeners
  Object.keys(documentEventListeners).forEach(
    (k) => delete documentEventListeners[k],
  );
  // Ensure global.fetch is always set to mockFetch
  global.fetch = mockFetch;
  // Restore original document methods that might have been overwritten
  mockDocument.querySelector = originalQuerySelector;
  mockDocument.querySelectorAll = originalQuerySelectorAll;
}

function getDocumentEventListeners() {
  return documentEventListeners;
}

function getFetchCalls() {
  return fetchCalls;
}
function setFetchResponse(url, response) {
  fetchResponses[url] = response;
}
function setDefaultFetchResponse(response) {
  defaultFetchResponse = response;
}
function getElement(id) {
  return mockElements[id];
}

module.exports = {
  mockLocalStorage,
  mockElements,
  browserGlobals,
  createMockElement,
  resetMocks,
  getFetchCalls,
  setFetchResponse,
  setDefaultFetchResponse,
  getElement,
  MockTerminal,
  MockFitAddon,
  createMockAceEditor,
  getDocumentEventListeners,
};

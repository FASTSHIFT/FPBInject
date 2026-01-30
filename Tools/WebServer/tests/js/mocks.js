/**
 * Browser Environment Mocks
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
  return {
    id,
    value: '',
    _textContent: '',
    get textContent() {
      return this._textContent;
    },
    set textContent(v) {
      this._textContent = v;
      this._innerHTML = v
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    },
    _innerHTML: '',
    get innerHTML() {
      return this._innerHTML;
    },
    set innerHTML(v) {
      this._innerHTML = v;
    },
    className: '',
    style: {
      display: '',
      opacity: '',
      width: '',
      height: '',
      background: '',
      visibility: '',
      pointerEvents: '',
    },
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
        if (force !== undefined)
          force ? this._classes.add(cls) : this._classes.delete(cls);
        else
          this._classes.has(cls)
            ? this._classes.delete(cls)
            : this._classes.add(cls);
        return this._classes.has(cls);
      },
    },
    _eventListeners: {},
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
    appendChild(child) {
      return child;
    },
    removeChild(child) {
      return child;
    },
    remove() {},
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    getAttribute(name) {
      return this[`_attr_${name}`] || null;
    },
    setAttribute(name, value) {
      this[`_attr_${name}`] = value;
    },
    closest() {
      return null;
    },
    checked: false,
    disabled: false,
    open: false,
    tagName: 'DIV',
    title: '',
    options: [],
    selectedIndex: 0,
  };
}

let fetchCalls = [];
let fetchResponses = {};

const mockFetch = async (url, options = {}) => {
  fetchCalls.push({ url, options });
  const response = fetchResponses[url] || { success: true };
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => response,
    text: async () => JSON.stringify(response),
    body: { getReader: () => ({ read: async () => ({ done: true }) }) },
  };
};

const browserGlobals = {
  localStorage: mockLocalStorage,
  document: {
    getElementById(id) {
      if (!mockElements[id]) mockElements[id] = createMockElement(id);
      return mockElements[id];
    },
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    createElement(tag) {
      const el = createMockElement(`_created_${tag}_${Date.now()}`);
      el.tagName = tag.toUpperCase();
      return el;
    },
    addEventListener() {},
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
  },
  window: null,
  navigator: {
    clipboard: {
      writeText() {
        return Promise.resolve();
      },
    },
  },
  console,
  setTimeout: (fn) => {
    fn();
    return 1;
  },
  clearTimeout: () => {},
  setInterval: () => 1,
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
  encodeURIComponent,
  decodeURIComponent,
  fetch: mockFetch,
  alert() {},
  confirm() {
    return true;
  },
  requestAnimationFrame(cb) {
    cb();
    return 1;
  },
  getComputedStyle() {
    return { getPropertyValue: () => '300px' };
  },
  Terminal: class {
    constructor(opts) {
      this.options = opts || {};
    }
    open() {}
    loadAddon() {}
    writeln(msg) {
      this._lastWrite = msg;
    }
    write(msg) {
      this._lastWrite = msg;
    }
    clear() {
      this._cleared = true;
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
  },
  FitAddon: {
    FitAddon: class {
      fit() {
        this._fitted = true;
      }
    },
  },
  ace: {
    edit() {
      return {
        _value: '',
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
        setValue(v) {
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
      };
    },
  },
  hljs: { highlightElement() {} },
};

browserGlobals.window = {
  localStorage: browserGlobals.localStorage,
  document: browserGlobals.document,
  navigator: browserGlobals.navigator,
  fetch: browserGlobals.fetch,
  alert: browserGlobals.alert,
  confirm: browserGlobals.confirm,
  addEventListener() {},
  FPBState: null,
};

function resetMocks() {
  mockLocalStorage.clear();
  fetchCalls = [];
  Object.keys(mockElements).forEach((k) => delete mockElements[k]);
}

function getFetchCalls() {
  return fetchCalls;
}
function setFetchResponse(url, response) {
  fetchResponses[url] = response;
}

module.exports = {
  mockLocalStorage,
  mockElements,
  browserGlobals,
  createMockElement,
  resetMocks,
  getFetchCalls,
  setFetchResponse,
};

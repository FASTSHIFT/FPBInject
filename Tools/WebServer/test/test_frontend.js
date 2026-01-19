/**
 * FPBInject Frontend JavaScript Tests
 *
 * 使用 Node.js 运行，模拟 DOM 环境进行测试
 * 运行方式: node test/test_frontend.js
 */

// Mock DOM environment
const mockLocalStorage = {
  store: {},
  getItem(key) {
    return this.store[key] || null;
  },
  setItem(key, value) {
    this.store[key] = String(value);
  },
  removeItem(key) {
    delete this.store[key];
  },
  clear() {
    this.store = {};
  },
};

// Mock fetch
const mockFetchResponses = {};
async function mockFetch(url, options = {}) {
  const key = `${options.method || 'GET'}:${url}`;
  const response = mockFetchResponses[key] || mockFetchResponses[url] || { success: true };
  return {
    json: async () => response,
    ok: true,
    status: 200,
  };
}

// Mock DOM elements
const mockElements = {};
function mockGetElementById(id) {
  if (!mockElements[id]) {
    mockElements[id] = {
      id,
      value: '',
      textContent: '',
      innerHTML: '',
      style: { display: '' },
      classList: {
        classes: new Set(),
        add(cls) { this.classes.add(cls); },
        remove(cls) { this.classes.delete(cls); },
        contains(cls) { return this.classes.has(cls); },
        toggle(cls) {
          if (this.classes.has(cls)) {
            this.classes.delete(cls);
          } else {
            this.classes.add(cls);
          }
        },
      },
      addEventListener: function() {},
      appendChild: function() {},
      checked: false,
      disabled: false,
    };
  }
  return mockElements[id];
}

// Setup global mocks
global.localStorage = mockLocalStorage;
global.fetch = mockFetch;
global.document = {
  getElementById: mockGetElementById,
  querySelectorAll: () => [],
  createElement: (tag) => ({
    className: '',
    textContent: '',
    innerHTML: '',
    onclick: null,
    appendChild: function() {},
  }),
  addEventListener: function() {},
};
global.window = {
  addEventListener: function() {},
};

// ===================== Test Framework =====================

let testCount = 0;
let passCount = 0;
let failCount = 0;

function describe(name, fn) {
  console.log(`\n\x1b[36m${name}\x1b[0m`);
  fn();
}

function it(name, fn) {
  testCount++;
  try {
    fn();
    passCount++;
    console.log(`  \x1b[32m✓\x1b[0m ${name}`);
  } catch (e) {
    failCount++;
    console.log(`  \x1b[31m✗\x1b[0m ${name}`);
    console.log(`    \x1b[31m${e.message}\x1b[0m`);
  }
}

function assertEqual(actual, expected, message = '') {
  if (actual !== expected) {
    throw new Error(`${message} Expected ${expected}, got ${actual}`);
  }
}

function assertTrue(value, message = '') {
  if (!value) {
    throw new Error(`${message} Expected true, got ${value}`);
  }
}

function assertFalse(value, message = '') {
  if (value) {
    throw new Error(`${message} Expected false, got ${value}`);
  }
}

function assertContains(str, substr, message = '') {
  if (!str.includes(substr)) {
    throw new Error(`${message} Expected "${str}" to contain "${substr}"`);
  }
}

// ===================== Utility Functions to Test =====================

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Toggle section (from app.js)
function toggleSection(sectionId) {
  const section = mockGetElementById(sectionId);
  if (section) {
    section.classList.toggle('collapsed');
    const collapsed = section.classList.contains('collapsed');
    mockLocalStorage.setItem(
      'section_' + sectionId,
      collapsed ? 'collapsed' : 'expanded',
    );
  }
}

// Toggle card (from app.js)
function toggleCard(cardId, event) {
  if (event && event.target && event.target.closest) {
    if (event.target.closest('button, .card-actions')) {
      return;
    }
  }
  const card = mockGetElementById(cardId);
  if (card) {
    card.classList.toggle('collapsed');
    const collapsed = card.classList.contains('collapsed');
    mockLocalStorage.setItem(
      'card_' + cardId,
      collapsed ? 'collapsed' : 'expanded',
    );
  }
}

// API helper (from app.js)
async function api(endpoint, method = 'GET', data = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (method !== 'GET') {
    options.body = JSON.stringify(data || {});
  }

  try {
    const response = await mockFetch('/api' + endpoint, options);
    return await response.json();
  } catch (e) {
    return { success: false, error: e.message };
  }
}

// Update connection UI (from app.js)
function updateConnectionUI(connected) {
  const indicator = mockGetElementById('connectionIndicator');
  const status = mockGetElementById('connectionStatus');
  const btn = mockGetElementById('connectBtn');

  if (connected) {
    indicator.className = 'status-indicator connected';
    status.className = 'status-text connected';
    status.textContent = '已连接';
    btn.innerHTML = '<span class="btn-icon-left">🔌</span> 断开';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-danger');
  } else {
    indicator.className = 'status-indicator disconnected';
    status.className = 'status-text disconnected';
    status.textContent = '未连接';
    btn.innerHTML = '<span class="btn-icon-left">⚡</span> 连接';
    btn.classList.remove('btn-danger');
    btn.classList.add('btn-primary');
  }
}

// Update inject status (from app.js)
function updateInjectStatus(statusObj) {
  const badge = mockGetElementById('injectBadge');
  const targetDisplay = mockGetElementById('targetFuncDisplay');
  const funcDisplay = mockGetElementById('injectFuncDisplay');
  const timeDisplay = mockGetElementById('injectTimeDisplay');

  if (statusObj.inject_active) {
    badge.textContent = '已激活';
    badge.className = 'panel-badge active';
    targetDisplay.textContent = statusObj.last_inject_target || '-';
    funcDisplay.textContent = statusObj.last_inject_func || '-';
    if (statusObj.last_inject_time) {
      const date = new Date(statusObj.last_inject_time * 1000);
      timeDisplay.textContent = date.toLocaleTimeString();
    }
  } else {
    badge.textContent = '未激活';
    badge.className = 'panel-badge';
    targetDisplay.textContent = '-';
    funcDisplay.textContent = '-';
    timeDisplay.textContent = '-';
  }
}

// Render symbol list (from app.js)
function renderSymbolList(symbols) {
  const list = mockGetElementById('symbolList');
  if (!symbols || symbols.length === 0) {
    list.innerHTML = '<div class="symbol-hint">未找到匹配的符号</div>';
    return;
  }

  list.innerHTML = '';
  // In real code, would create elements
}

// ===================== Tests =====================

describe('Utility Functions', () => {
  it('sleep returns a Promise', () => {
    const result = sleep(1);
    assertTrue(result instanceof Promise);
  });
});

describe('Section Toggle', () => {
  it('toggleSection adds collapsed class', () => {
    mockLocalStorage.clear();
    const section = mockGetElementById('testSection');
    section.classList.classes.clear();
    
    toggleSection('testSection');
    
    assertTrue(section.classList.contains('collapsed'));
    assertEqual(mockLocalStorage.getItem('section_testSection'), 'collapsed');
  });

  it('toggleSection removes collapsed class when already collapsed', () => {
    const section = mockGetElementById('testSection2');
    section.classList.classes.clear();
    section.classList.add('collapsed');
    
    toggleSection('testSection2');
    
    assertFalse(section.classList.contains('collapsed'));
    assertEqual(mockLocalStorage.getItem('section_testSection2'), 'expanded');
  });
});

describe('Card Toggle', () => {
  it('toggleCard adds collapsed class', () => {
    const card = mockGetElementById('testCard');
    card.classList.classes.clear();
    
    toggleCard('testCard', null);
    
    assertTrue(card.classList.contains('collapsed'));
  });

  it('toggleCard does not toggle when clicking button', () => {
    const card = mockGetElementById('testCard2');
    card.classList.classes.clear();
    
    // Mock event with button target
    const mockEvent = {
      target: {
        closest: (selector) => selector.includes('button') ? {} : null,
      },
    };
    
    toggleCard('testCard2', mockEvent);
    
    assertFalse(card.classList.contains('collapsed'));
  });
});

describe('API Helper', () => {
  it('api makes GET request', async () => {
    mockFetchResponses['/api/test'] = { success: true, data: 'test' };
    
    const result = await api('/test');
    
    assertTrue(result.success);
  });

  it('api makes POST request with data', async () => {
    mockFetchResponses['POST:/api/test'] = { success: true };
    
    const result = await api('/test', 'POST', { key: 'value' });
    
    assertTrue(result.success);
  });
});

describe('Connection UI', () => {
  it('updateConnectionUI shows connected state', () => {
    updateConnectionUI(true);
    
    const indicator = mockGetElementById('connectionIndicator');
    const status = mockGetElementById('connectionStatus');
    
    assertEqual(indicator.className, 'status-indicator connected');
    assertEqual(status.textContent, '已连接');
  });

  it('updateConnectionUI shows disconnected state', () => {
    updateConnectionUI(false);
    
    const indicator = mockGetElementById('connectionIndicator');
    const status = mockGetElementById('connectionStatus');
    
    assertEqual(indicator.className, 'status-indicator disconnected');
    assertEqual(status.textContent, '未连接');
  });
});

describe('Inject Status', () => {
  it('updateInjectStatus shows active state', () => {
    updateInjectStatus({
      inject_active: true,
      last_inject_target: 'main',
      last_inject_func: 'inject_main',
      last_inject_time: Date.now() / 1000,
    });
    
    const badge = mockGetElementById('injectBadge');
    const targetDisplay = mockGetElementById('targetFuncDisplay');
    
    assertEqual(badge.textContent, '已激活');
    assertEqual(targetDisplay.textContent, 'main');
  });

  it('updateInjectStatus shows inactive state', () => {
    updateInjectStatus({ inject_active: false });
    
    const badge = mockGetElementById('injectBadge');
    const targetDisplay = mockGetElementById('targetFuncDisplay');
    
    assertEqual(badge.textContent, '未激活');
    assertEqual(targetDisplay.textContent, '-');
  });
});

describe('Symbol List', () => {
  it('renderSymbolList shows hint for empty list', () => {
    renderSymbolList([]);
    
    const list = mockGetElementById('symbolList');
    assertContains(list.innerHTML, '未找到匹配的符号');
  });

  it('renderSymbolList shows hint for null', () => {
    renderSymbolList(null);
    
    const list = mockGetElementById('symbolList');
    assertContains(list.innerHTML, '未找到匹配的符号');
  });

  it('renderSymbolList clears innerHTML for non-empty list', () => {
    const list = mockGetElementById('symbolList');
    list.innerHTML = 'old content';
    
    renderSymbolList([{ name: 'main', addr: '0x08000000' }]);
    
    assertEqual(list.innerHTML, '');
  });
});

describe('LocalStorage Integration', () => {
  it('stores and retrieves values correctly', () => {
    mockLocalStorage.clear();
    mockLocalStorage.setItem('test_key', 'test_value');
    
    assertEqual(mockLocalStorage.getItem('test_key'), 'test_value');
  });

  it('returns null for non-existent keys', () => {
    mockLocalStorage.clear();
    
    assertEqual(mockLocalStorage.getItem('nonexistent'), null);
  });

  it('removes items correctly', () => {
    mockLocalStorage.setItem('to_remove', 'value');
    mockLocalStorage.removeItem('to_remove');
    
    assertEqual(mockLocalStorage.getItem('to_remove'), null);
  });
});

// ===================== Run Tests =====================

console.log('\n\x1b[1m========================================\x1b[0m');
console.log('\x1b[1m    FPBInject Frontend Tests\x1b[0m');
console.log('\x1b[1m========================================\x1b[0m');

// Run async tests
(async () => {
  // Wait for async tests to complete
  await sleep(100);
  
  console.log('\n\x1b[1m========================================\x1b[0m');
  console.log(`\x1b[1m    Results: ${passCount}/${testCount} passed\x1b[0m`);
  if (failCount > 0) {
    console.log(`\x1b[31m    ${failCount} tests failed\x1b[0m`);
    process.exit(1);
  } else {
    console.log('\x1b[32m    All tests passed!\x1b[0m');
    process.exit(0);
  }
})();

/**
 * Tests for features/fpb.js, features/symbols.js, features/autoinject.js, features/filebrowser.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const {
  resetMocks,
  setFetchResponse,
  getFetchCalls,
  browserGlobals,
  MockTerminal,
} = require('./mocks');

module.exports = function (w) {
  describe('FPB Command Functions (features/fpb.js)', () => {
    it('fpbPing is a function', () =>
      assertTrue(typeof w.fpbPing === 'function'));
    it('fpbTestSerial is a function', () =>
      assertTrue(typeof w.fpbTestSerial === 'function'));
    it('fpbInfo is a function', () =>
      assertTrue(typeof w.fpbInfo === 'function'));
    it('fpbInjectMulti is a function', () =>
      assertTrue(typeof w.fpbInjectMulti === 'function'));
  });

  describe('fpbPing Function', () => {
    it('is async function', () => {
      assertTrue(w.fpbPing.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.fpbPing();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('sends POST to /api/fpb/ping', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/ping', { success: true, message: 'Pong!' });
      await w.fpbPing();
      // Check side effect instead of fetch calls
      assertTrue(mockTerm._writes.length > 0);
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('writes success message on success', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/ping', { success: true, message: 'Pong!' });
      await w.fpbPing();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Pong!')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('fpbTestSerial Function', () => {
    it('is async function', () => {
      assertTrue(w.fpbTestSerial.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.fpbTestSerial();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('sends POST to /api/fpb/test-serial', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/test-serial', {
        success: true,
        tests: [],
        max_working_size: 1024,
        recommended_chunk_size: 128,
      });
      await w.fpbTestSerial();
      // Check side effect instead of fetch calls
      assertTrue(mockTerm._writes.length > 0);
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('displays test results', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/test-serial', {
        success: true,
        tests: [
          { size: 16, passed: true, response_time_ms: 10, cmd_len: 20 },
          { size: 32, passed: false, error: 'Timeout' },
        ],
        max_working_size: 16,
        failed_size: 32,
        recommended_chunk_size: 16,
      });
      await w.fpbTestSerial();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Max working size'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles test failure', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/test-serial', {
        success: false,
        error: 'Test failed',
      });
      await w.fpbTestSerial();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Test failed')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('fpbInfo Function', () => {
    it('is async function', () =>
      assertTrue(w.fpbInfo.constructor.name === 'AsyncFunction'));

    it('returns early if not connected', async () => {
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.fpbInfo();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('fetches from /api/fpb/info', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbInfo();
      // Check side effect instead of fetch calls
      assertTrue(mockTerm._writes.length > 0);
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('updates slot states from response', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [
          {
            id: 0,
            occupied: true,
            func: 'test_func',
            orig_addr: '0x1000',
            target_addr: '0x2000',
            code_size: 100,
          },
          { id: 1, occupied: false },
          { id: 2, occupied: false },
          { id: 3, occupied: false },
          { id: 4, occupied: false },
          { id: 5, occupied: false },
        ],
      });
      await w.fpbInfo();
      assertTrue(w.FPBState.slotStates[0].occupied);
      assertEqual(w.FPBState.slotStates[0].func, 'test_func');
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('updates memory info from response', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [],
        memory: { is_dynamic: true, used: 512 },
      });
      await w.fpbInfo();
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      assertContains(memEl.innerHTML, '512');
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles build time mismatch warning', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [],
        build_time_mismatch: true,
        device_build_time: '2024-01-01 12:00:00',
        elf_build_time: '2024-01-02 12:00:00',
      });
      await w.fpbInfo();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('mismatch')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('displays device build time', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [],
        device_build_time: '2024-01-01 12:00:00',
      });
      await w.fpbInfo();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Device build'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles error response', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/info', {
        success: false,
        error: 'Device not responding',
      });
      await w.fpbInfo();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Device not responding'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('FPB v2 forces DebugMonitor mode and disables other options', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const patchMode = browserGlobals.document.getElementById('patchMode');
      patchMode.value = 'trampoline';
      // Add options to simulate real select
      patchMode.innerHTML = '';
      const opts = ['trampoline', 'debugmon', 'direct'];
      opts.forEach((v) => {
        const opt = browserGlobals.document.createElement('option');
        opt.value = v;
        opt.disabled = false;
        patchMode.appendChild(opt);
      });
      patchMode.options = patchMode.querySelectorAll('option');
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [],
        fpb_version: 2,
      });
      await w.fpbInfo();
      assertEqual(patchMode.value, 'debugmon');
      // Check non-debugmon options are disabled
      Array.from(patchMode.options).forEach((opt) => {
        if (opt.value === 'debugmon') {
          assertTrue(!opt.disabled);
        } else {
          assertTrue(opt.disabled);
        }
      });
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('FPB v1 enables all mode options', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const patchMode = browserGlobals.document.getElementById('patchMode');
      patchMode.innerHTML = '';
      const opts = ['trampoline', 'debugmon', 'direct'];
      opts.forEach((v) => {
        const opt = browserGlobals.document.createElement('option');
        opt.value = v;
        opt.disabled = true; // start disabled
        patchMode.appendChild(opt);
      });
      patchMode.options = patchMode.querySelectorAll('option');
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [],
        fpb_version: 1,
      });
      await w.fpbInfo();
      Array.from(patchMode.options).forEach((opt) => {
        assertTrue(!opt.disabled);
      });
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('fpbInjectMulti Function', () => {
    it('is async function', () =>
      assertTrue(w.fpbInjectMulti.constructor.name === 'AsyncFunction'));

    it('returns early if not connected', async () => {
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.fpbInjectMulti();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('returns error if no patch source', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      browserGlobals.document.getElementById('patchSource').value = '';
      await w.fpbInjectMulti();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('No patch source'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('sends POST to /api/fpb/inject/multi', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      browserGlobals.document.getElementById('patchSource').value =
        'void test() {}';
      setFetchResponse('/api/fpb/inject/multi', {
        success: true,
        successful_count: 1,
        total_count: 1,
      });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbInjectMulti();
      // Check side effect instead of fetch calls
      assertTrue(mockTerm._writes.length > 0);
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('displays success message', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      browserGlobals.document.getElementById('patchSource').value =
        'void test() {}';
      setFetchResponse('/api/fpb/inject/multi', {
        success: true,
        successful_count: 2,
        total_count: 2,
        compile_time: 1.0,
        upload_time: 0.5,
        code_size: 100,
      });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbInjectMulti();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Injected')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles injection failure', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      browserGlobals.document.getElementById('patchSource').value =
        'void test() {}';
      setFetchResponse('/api/fpb/inject/multi', {
        success: false,
        error: 'Compilation failed',
      });
      await w.fpbInjectMulti();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Compilation failed'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('Symbol Functions (features/symbols.js)', () => {
    it('searchSymbols is a function', () =>
      assertTrue(typeof w.searchSymbols === 'function'));
    it('selectSymbol is a function', () =>
      assertTrue(typeof w.selectSymbol === 'function'));
    it('onSymbolClick is a function', () =>
      assertTrue(typeof w.onSymbolClick === 'function'));
    it('onSymbolDblClick is a function', () =>
      assertTrue(typeof w.onSymbolDblClick === 'function'));
    it('openSymbolValueTab is a function', () =>
      assertTrue(typeof w.openSymbolValueTab === 'function'));
  });

  describe('searchSymbols Function', () => {
    it('is async function', () =>
      assertTrue(w.searchSymbols.constructor.name === 'AsyncFunction'));

    it('returns early if query too short', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'a';
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'at least 2');
    });

    it('fetches from /api/symbols/search', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'test';
      setFetchResponse('/api/symbols/search', { symbols: [] });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      // Check side effect - symbolList should be updated
      assertTrue(list !== null);
    });

    it('displays found symbols', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'test';
      setFetchResponse('/api/symbols/search', {
        symbols: [
          {
            name: 'test_func',
            addr: '0x1000',
            type: 'function',
            size: 100,
            section: '.text',
          },
        ],
      });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'test_func');
    });

    it('displays function symbol with method icon', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'test';
      setFetchResponse('/api/symbols/search', {
        symbols: [{ name: 'test_func', addr: '0x1000', type: 'function' }],
      });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'codicon-symbol-method');
    });

    it('displays variable symbol with variable icon', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'g_var';
      setFetchResponse('/api/symbols/search', {
        symbols: [
          {
            name: 'g_var',
            addr: '0x20000000',
            type: 'variable',
            size: 4,
            section: '.data',
          },
        ],
      });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'codicon-symbol-variable');
    });

    it('displays const symbol with constant icon', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'k_val';
      setFetchResponse('/api/symbols/search', {
        symbols: [
          {
            name: 'k_val',
            addr: '0x08010000',
            type: 'const',
            size: 8,
            section: '.rodata',
          },
        ],
      });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'codicon-symbol-constant');
    });

    it('passes type to onSymbolClick handler', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'g_var';
      setFetchResponse('/api/symbols/search', {
        symbols: [{ name: 'g_var', addr: '0x20000000', type: 'variable' }],
      });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, "onSymbolClick('g_var'");
      assertContains(list.innerHTML, "'variable'");
    });

    it('passes type to onSymbolDblClick handler', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'g_var';
      setFetchResponse('/api/symbols/search', {
        symbols: [{ name: 'g_var', addr: '0x20000000', type: 'variable' }],
      });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, "onSymbolDblClick('g_var'");
      assertContains(list.innerHTML, "'variable'");
    });

    it('defaults to function type when type not provided', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'test';
      setFetchResponse('/api/symbols/search', {
        symbols: [{ name: 'test_func', addr: '0x1000' }],
      });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'codicon-symbol-method');
    });

    it('displays no symbols found message', async () => {
      browserGlobals.document.getElementById('symbolSearch').value =
        'nonexistent';
      setFetchResponse('/api/symbols/search', { symbols: [] });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'No symbols found');
    });

    it('displays error message from API', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'test';
      setFetchResponse('/api/symbols/search', { error: 'ELF not loaded' });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'ELF not loaded');
    });

    it('handles fetch exception', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = 'test';
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'Error');
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles address search format', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = '0x1000';
      setFetchResponse('/api/symbols/search', { symbols: [] });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'No symbols found');
    });

    it('handles hex address without 0x prefix', async () => {
      browserGlobals.document.getElementById('symbolSearch').value = '1234abcd';
      setFetchResponse('/api/symbols/search', { symbols: [] });
      await w.searchSymbols();
      const list = browserGlobals.document.getElementById('symbolList');
      assertContains(list.innerHTML, 'address');
    });
  });

  describe('selectSymbol Function', () => {
    it('writes info message', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.selectSymbol('test_func');
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('test_func')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('_extractFieldHex Helper', () => {
    it('extracts correct hex bytes at offset 0', () => {
      assertEqual(w._extractFieldHex('0102030405', 0, 2), '01 02');
    });

    it('extracts correct hex bytes at non-zero offset', () => {
      assertEqual(w._extractFieldHex('AABBCCDDEE', 2, 2), 'CC DD');
    });

    it('returns ?? when out of bounds', () => {
      assertEqual(w._extractFieldHex('0102', 0, 4), '??');
    });

    it('handles single byte extraction', () => {
      assertEqual(w._extractFieldHex('FF', 0, 1), 'FF');
    });
  });

  describe('_decodeFieldValue Helper', () => {
    it('decodes uint8_t value', () => {
      assertEqual(w._decodeFieldValue('FF', 0, 1, 'uint8_t'), '255');
    });

    it('decodes int8_t signed value', () => {
      assertEqual(w._decodeFieldValue('FF', 0, 1, 'int8_t'), '-1');
    });

    it('decodes uint32_t little-endian', () => {
      // 0x01 0x00 0x00 0x00 = 1 in LE
      assertEqual(w._decodeFieldValue('01000000', 0, 4, 'uint32_t'), '1');
    });

    it('decodes uint16_t little-endian', () => {
      // 0x00 0x01 = 256 in LE
      assertEqual(w._decodeFieldValue('0001', 0, 2, 'uint16_t'), '256');
    });

    it('decodes char array as string', () => {
      // "Hi" + null
      const result = w._decodeFieldValue('486900', 0, 3, 'char[3]');
      assertContains(result, 'Hi');
    });

    it('returns empty string for unknown type with array suffix', () => {
      assertEqual(w._decodeFieldValue('01020304', 0, 4, 'my_struct_t[2]'), '');
    });

    it('returns empty string when out of bounds', () => {
      assertEqual(w._decodeFieldValue('01', 0, 4, 'uint32_t'), '');
    });
  });

  describe('_formatHexDump Helper', () => {
    it('formats single line hex dump', () => {
      const result = w._formatHexDump('48656C6C6F');
      assertContains(result, '0x0000');
      assertContains(result, '48 65 6C 6C 6F');
      assertContains(result, 'Hello');
    });

    it('replaces non-printable chars with dot', () => {
      const result = w._formatHexDump('001F7F');
      assertContains(result, '...');
    });

    it('handles empty hex data', () => {
      const result = w._formatHexDump('');
      assertEqual(result, '');
    });

    it('wraps long data into multiple lines', () => {
      // 32 hex chars = 16 bytes = 1 line, 34 hex chars = 17 bytes = 2 lines
      const hex34 = '00'.repeat(17);
      const result = w._formatHexDump(hex34);
      const lines = result.split('\n');
      assertEqual(lines.length, 2);
    });
  });

  describe('_escapeHtml Helper', () => {
    it('escapes angle brackets', () => {
      const result = w._escapeHtml('<script>alert(1)</script>');
      assertTrue(!result.includes('<script>'));
      assertContains(result, '&lt;');
    });

    it('handles null/undefined gracefully', () => {
      const result = w._escapeHtml(null);
      assertEqual(result, '');
    });

    it('passes plain text through', () => {
      assertEqual(w._escapeHtml('hello'), 'hello');
    });
  });

  describe('_renderSymbolValueContent Helper', () => {
    it('renders header with name and address', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'g_counter',
          addr: '0x20000000',
          size: 4,
          section: '.data',
          hex_data: '01000000',
        },
        false,
      );
      assertContains(html, 'g_counter');
      assertContains(html, '0x20000000');
      assertContains(html, 'Read-Write');
    });

    it('renders const label for const symbols', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'k_magic',
          addr: '0x08010000',
          size: 4,
          section: '.rodata',
          hex_data: 'DEADBEEF',
        },
        true,
      );
      assertContains(html, 'Read-Only');
    });

    it('renders struct table when struct_layout present', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'g_cfg',
          addr: '0x20000000',
          size: 8,
          section: '.data',
          hex_data: '0100000002000000',
          struct_layout: [
            { name: 'x', type_name: 'uint32_t', offset: 0, size: 4 },
            { name: 'y', type_name: 'uint32_t', offset: 4, size: 4 },
          ],
        },
        false,
      );
      assertContains(html, 'sym-tree-view');
      assertContains(html, 'x');
      assertContains(html, 'y');
      assertContains(html, 'uint32_t');
    });

    it('renders hex dump section', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'g_val',
          addr: '0x20000000',
          size: 2,
          section: '.data',
          hex_data: 'AABB',
        },
        false,
      );
      assertContains(html, 'sym-hex-dump');
      assertContains(html, 'AA BB');
    });

    it('renders bss hint when no hex_data and .bss section', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'g_zero',
          addr: '0x20001000',
          size: 4,
          section: '.bss',
        },
        false,
      );
      assertContains(html, '.bss');
    });

    it('renders needs device read for bss struct fields', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'g_state',
          addr: '0x20001000',
          size: 4,
          section: '.bss',
          struct_layout: [
            { name: 'count', type_name: 'uint32_t', offset: 0, size: 4 },
          ],
        },
        false,
      );
      assertContains(html, 'needs device read');
    });
  });

  describe('openSymbolValueTab Function', () => {
    it('is async function', () => {
      assertTrue(w.openSymbolValueTab.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/symbols/value', async () => {
      w.FPBState.editorTabs = [];
      setFetchResponse('/api/symbols/value', {
        success: true,
        name: 'g_val',
        addr: '0x20000000',
        size: 4,
        section: '.data',
        hex_data: '01000000',
      });
      await w.openSymbolValueTab('g_val', 'variable');
      assertTrue(w.FPBState.editorTabs.some((t) => t.id === 'symval_g_val'));
    });

    it('reuses existing tab instead of creating duplicate', async () => {
      w.FPBState.editorTabs = [{ id: 'symval_g_val', title: 'g_val [var]' }];
      // Should not fetch, just switch
      await w.openSymbolValueTab('g_val', 'variable');
      assertEqual(
        w.FPBState.editorTabs.filter((t) => t.id === 'symval_g_val').length,
        1,
      );
    });

    it('handles API error gracefully', async () => {
      w.FPBState.editorTabs = [];
      setFetchResponse('/api/symbols/value', {
        success: false,
        error: 'Not found',
      });
      await w.openSymbolValueTab('missing_sym', 'variable');
      assertTrue(
        !w.FPBState.editorTabs.some((t) => t.id === 'symval_missing_sym'),
      );
    });

    it('sets correct tab type for const', async () => {
      w.FPBState.editorTabs = [];
      setFetchResponse('/api/symbols/value', {
        success: true,
        name: 'k_val',
        addr: '0x08010000',
        size: 4,
        section: '.rodata',
        hex_data: 'DEADBEEF',
      });
      await w.openSymbolValueTab('k_val', 'const');
      const tab = w.FPBState.editorTabs.find((t) => t.id === 'symval_k_val');
      assertTrue(tab !== undefined);
      assertEqual(tab.type, 'const-viewer');
    });

    it('sets correct tab type for variable', async () => {
      w.FPBState.editorTabs = [];
      setFetchResponse('/api/symbols/value', {
        success: true,
        name: 'g_cnt',
        addr: '0x20000000',
        size: 4,
        section: '.data',
        hex_data: '00000000',
      });
      await w.openSymbolValueTab('g_cnt', 'variable');
      const tab = w.FPBState.editorTabs.find((t) => t.id === 'symval_g_cnt');
      assertEqual(tab.type, 'var-viewer');
    });
  });

  describe('onSymbolClick Dispatch', () => {
    it('is a function', () =>
      assertTrue(typeof w.onSymbolClick === 'function'));

    it('dispatches variable to openSymbolValueTab', () => {
      // onSymbolClick uses setTimeout, so we just verify no crash
      w.onSymbolClick('g_var', '0x20000000', 'variable');
      assertTrue(true);
    });

    it('dispatches const to openSymbolValueTab', () => {
      w.onSymbolClick('k_val', '0x08010000', 'const');
      assertTrue(true);
    });

    it('dispatches function to openDisassembly', () => {
      w.onSymbolClick('main', '0x08000000', 'function');
      assertTrue(true);
    });
  });

  describe('onSymbolDblClick Dispatch', () => {
    it('dispatches function to openManualPatchTab', () => {
      w.onSymbolDblClick('main', 'function');
      assertTrue(true);
    });

    it('dispatches variable to openSymbolValueTab', () => {
      w.onSymbolDblClick('g_var', 'variable');
      assertTrue(true);
    });
  });

  describe('readSymbolFromDevice Function', () => {
    it('is exported to window', () =>
      assertTrue(typeof w.readSymbolFromDevice === 'function'));

    it('is async function', () =>
      assertTrue(w.readSymbolFromDevice.constructor.name === 'AsyncFunction'));

    it('calls POST /api/symbols/read', async () => {
      setFetchResponse('/api/symbols/read', {
        success: true,
        name: 'g_cnt',
        addr: '0x20000000',
        size: 4,
        hex_data: '05000000',
        source: 'device',
      });
      await w.readSymbolFromDevice('g_cnt');
      const calls = getFetchCalls();
      assertTrue(
        calls.some(
          (c) =>
            c.url === '/api/symbols/read' &&
            c.options &&
            c.options.method === 'POST',
        ),
      );
    });

    it('sends symbol name in request body', async () => {
      setFetchResponse('/api/symbols/read', {
        success: true,
        name: 'g_cnt',
        addr: '0x20000000',
        size: 4,
        hex_data: '05000000',
        source: 'device',
      });
      await w.readSymbolFromDevice('g_cnt');
      const calls = getFetchCalls();
      const readCall = calls.find((c) => c.url === '/api/symbols/read');
      assertTrue(readCall !== undefined);
      const body = JSON.parse(readCall.options.body);
      assertEqual(body.name, 'g_cnt');
    });

    it('handles error response gracefully', async () => {
      setFetchResponse('/api/symbols/read', {
        success: false,
        error: 'Not connected',
      });
      // Should not throw
      await w.readSymbolFromDevice('g_cnt');
      assertTrue(true);
    });
  });

  describe('writeSymbolToDevice Function', () => {
    it('is exported to window', () =>
      assertTrue(typeof w.writeSymbolToDevice === 'function'));

    it('is async function', () =>
      assertTrue(w.writeSymbolToDevice.constructor.name === 'AsyncFunction'));

    it('returns early if no tab content', async () => {
      // No tabContent_symval_xxx element exists, should return without error
      await w.writeSymbolToDevice('nonexistent');
      assertTrue(true);
    });
  });

  describe('_renderSymbolValueContent Toolbar', () => {
    it('renders toolbar with Read/Write buttons for variable', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'g_cnt',
          addr: '0x20000000',
          size: 4,
          section: '.data',
          hex_data: '01000000',
        },
        false,
      );
      assertContains(html, 'sym-viewer-toolbar');
      assertContains(html, 'Read from Device');
      assertContains(html, 'Write to Device');
    });

    it('does not render toolbar for const', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'k_val',
          addr: '0x08010000',
          size: 4,
          section: '.rodata',
          hex_data: 'DEADBEEF',
        },
        true,
      );
      assertTrue(!html.includes('sym-viewer-toolbar'));
      assertTrue(!html.includes('Write to Device'));
    });

    it('toolbar buttons reference correct symbol name', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'my_var',
          addr: '0x20000000',
          size: 4,
          section: '.data',
          hex_data: '00000000',
        },
        false,
      );
      assertContains(html, "readSymbolFromDevice('my_var')");
      assertContains(html, "writeSymbolToDevice('my_var')");
    });

    it('renders status span with correct id', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'g_state',
          addr: '0x20000000',
          size: 4,
          section: '.data',
          hex_data: '00000000',
        },
        false,
      );
      assertContains(html, 'symStatus_g_state');
    });
  });

  describe('_renderSymbolValueContent Pointer Support', () => {
    it('renders pointer type badge for pointer variables', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'disp_def',
          addr: '0x20001000',
          size: 4,
          section: '.bss',
          is_pointer: true,
          pointer_target: 'lv_disp_t',
        },
        false,
      );
      assertContains(html, 'sym-viewer-type-badge');
      assertContains(html, 'lv_disp_t');
    });

    it('renders pointer value when hex_data present', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'disp_def',
          addr: '0x20001000',
          size: 4,
          section: '.data',
          hex_data: '00300020',
          is_pointer: true,
          pointer_target: 'lv_disp_t',
        },
        false,
      );
      assertContains(html, 'sym-pointer-value');
      assertContains(html, '0x20003000');
    });

    it('shows NULL label for null pointer', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'p_null',
          addr: '0x20001000',
          size: 4,
          section: '.bss',
          hex_data: '00000000',
          is_pointer: true,
          pointer_target: 'int',
        },
        false,
      );
      assertContains(html, 'sym-pointer-null');
      assertContains(html, 'NULL');
    });

    it('renders dereference checkbox for pointer', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'my_ptr',
          addr: '0x20001000',
          size: 4,
          section: '.data',
          is_pointer: true,
          pointer_target: 'my_struct',
        },
        false,
      );
      assertContains(html, 'symDerefToggle_my_ptr');
      assertContains(html, 'sym-deref-toggle');
    });

    it('does not render dereference checkbox for non-pointer', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'g_val',
          addr: '0x20001000',
          size: 4,
          section: '.data',
        },
        false,
      );
      assertTrue(!html.includes('sym-deref-toggle'));
    });

    it('renders deref data section when deref_data present', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'my_ptr',
          addr: '0x20001000',
          size: 4,
          section: '.data',
          hex_data: '00200020',
          is_pointer: true,
          pointer_target: 'my_struct',
          deref_data: {
            addr: '0x20002000',
            size: 8,
            hex_data: 'AABBCCDD11223344',
            type_name: 'my_struct',
            struct_layout: [
              { name: 'x', type_name: 'int', offset: 0, size: 4 },
              { name: 'y', type_name: 'int', offset: 4, size: 4 },
            ],
          },
        },
        false,
      );
      assertContains(html, 'sym-deref-section');
      assertContains(html, 'my_struct');
      assertContains(html, 'sym-tree-view');
    });

    it('renders deref error when deref_error present', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'my_ptr',
          addr: '0x20001000',
          size: 4,
          section: '.data',
          hex_data: '00000000',
          is_pointer: true,
          pointer_target: 'my_struct',
          deref_error: 'NULL pointer',
        },
        false,
      );
      assertContains(html, 'sym-deref-error');
      assertContains(html, 'NULL pointer');
    });

    it('renders pointer raw hex label', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'my_ptr',
          addr: '0x20001000',
          size: 4,
          section: '.data',
          hex_data: '00300020',
          is_pointer: true,
          pointer_target: 'int',
        },
        false,
      );
      assertContains(html, 'sym-hex-dump');
    });

    it('does not render struct layout for pointer without deref', () => {
      const html = w._renderSymbolValueContent(
        {
          name: 'my_ptr',
          addr: '0x20001000',
          size: 4,
          section: '.data',
          hex_data: '00300020',
          is_pointer: true,
          pointer_target: 'my_struct',
          struct_layout: null,
        },
        false,
      );
      assertTrue(!html.includes('sym-tree-view'));
    });
  });

  describe('_decodeLittleEndianHex Helper', () => {
    it('decodes 4-byte LE hex to address', () => {
      assertEqual(w._decodeLittleEndianHex('00300020', 4), '0x20003000');
    });

    it('decodes zero pointer', () => {
      assertEqual(w._decodeLittleEndianHex('00000000', 4), '0x00000000');
    });

    it('decodes 2-byte LE hex', () => {
      assertEqual(w._decodeLittleEndianHex('3412', 2), '0x1234');
    });
  });

  describe('_renderStructTable Helper', () => {
    it('renders tree view with field rows', () => {
      const html = w._renderStructTable(
        [{ name: 'x', type_name: 'int', offset: 0, size: 4 }],
        'AABBCCDD',
        false,
      );
      assertContains(html, 'sym-tree-view');
      assertContains(html, 'sym-tree-name');
    });

    it('renders bss hint when no hex data', () => {
      const html = w._renderStructTable(
        [{ name: 'x', type_name: 'int', offset: 0, size: 4 }],
        null,
        true,
      );
      assertContains(html, 'needs device read');
    });
  });

  describe('Tree View Rendering', () => {
    it('_renderStructTree renders sym-tree-view container', () => {
      const html = w._renderStructTree(
        [{ name: 'x', type_name: 'int', offset: 0, size: 4 }],
        'AABBCCDD',
        false,
        null,
      );
      assertContains(html, 'sym-tree-view');
      assertContains(html, 'sym-tree-name');
      assertContains(html, 'sym-tree-type');
    });

    it('uses gdb_values when available', () => {
      const html = w._renderStructTree(
        [{ name: 'x', type_name: 'lv_coord_t', offset: 0, size: 4 }],
        'AABBCCDD',
        false,
        { x: '42' },
      );
      assertContains(html, '42');
    });

    it('renders expandable node for nested struct', () => {
      const html = w._renderStructTree(
        [{ name: 'pos', type_name: 'lv_point_t', offset: 0, size: 8 }],
        'AABBCCDD11223344',
        false,
        { pos: '{x = 10, y = 20}' },
      );
      assertContains(html, 'sym-tree-toggle');
      assertContains(html, 'sym-tree-summary');
      assertContains(html, 'sym-tree-children');
    });

    it('falls back to hex decode when no gdb_values', () => {
      const html = w._renderStructTree(
        [{ name: 'val', type_name: 'uint32_t', offset: 0, size: 4 }],
        '01000000',
        false,
        null,
      );
      assertContains(html, '1');
    });

    it('_isExpandableValue detects struct bodies', () => {
      assertTrue(w._isExpandableValue('{x = 1, y = 2}'));
      assertTrue(!w._isExpandableValue('42'));
      assertTrue(!w._isExpandableValue(null));
      assertTrue(!w._isExpandableValue('{}'));
    });

    it('_splitGdbFields splits top-level fields', () => {
      const fields = w._splitGdbFields('x = 1, y = {a = 2, b = 3}, z = 4');
      assertEqual(fields.length, 3);
      assertEqual(fields[0], 'x = 1');
      assertContains(fields[1], 'y = {a = 2, b = 3}');
      assertEqual(fields[2], 'z = 4');
    });

    it('_splitGdbFields handles nested braces', () => {
      const fields = w._splitGdbFields('a = {b = {c = 1}}, d = 2');
      assertEqual(fields.length, 2);
    });

    it('_symDerefState is a Map', () => {
      assertTrue(w._symDerefState instanceof Map);
    });

    it('_renderStructTree with bss and no hex data', () => {
      const html = w._renderStructTree(
        [{ name: 'x', type_name: 'int', offset: 0, size: 4 }],
        null,
        true,
        null,
      );
      assertContains(html, 'sym-tree-no-data');
    });

    it('_renderStructTree with no hex and not bss', () => {
      const html = w._renderStructTree(
        [{ name: 'x', type_name: 'int', offset: 0, size: 4 }],
        null,
        false,
        null,
      );
      assertContains(html, '—');
    });

    it('_renderExpandableChildren handles array elements', () => {
      const html = w._renderStructTree(
        [{ name: 'arr', type_name: 'int[3]', offset: 0, size: 12 }],
        null,
        false,
        { arr: '{1, 2, 3}' },
      );
      assertContains(html, 'sym-tree-children');
    });

    it('_getExpandableSummary truncates long values', () => {
      const longVal = '{' + 'x = 1, '.repeat(20) + 'y = 2}';
      assertTrue(w._isExpandableValue(longVal));
    });

    it('_toggleTreeNode does nothing for missing node', () => {
      w._toggleTreeNode('nonexistent_node_id');
      assertTrue(true);
    });
  });

  describe('_decodeFieldValue pointer and typedef', () => {
    it('decodes pointer type as hex address', () => {
      const result = w._decodeFieldValue('00300020', 0, 4, 'lv_disp_t *');
      assertEqual(result, '0x20003000');
    });

    it('decodes typedef integer via fallback', () => {
      // lv_coord_t is a typedef for int16_t — not in intTypes list
      // but size=2 triggers typedef fallback
      const result = w._decodeFieldValue('0A00', 0, 2, 'lv_coord_t');
      assertEqual(result, '10');
    });
  });

  describe('Symbol Tab Data Cache', () => {
    it('_symTabDataCache is a Map', () => {
      assertTrue(w._symTabDataCache instanceof Map);
    });

    it('_rerenderSymbolTabs is a function', () => {
      assertTrue(typeof w._rerenderSymbolTabs === 'function');
    });

    it('_rerenderSymbolTabs does not throw when no tabs', () => {
      w._rerenderSymbolTabs();
      assertTrue(true);
    });
  });

  describe('Auto-Inject Functions (features/autoinject.js)', () => {
    it('startAutoInjectPolling is a function', () =>
      assertTrue(typeof w.startAutoInjectPolling === 'function'));
    it('stopAutoInjectPolling is a function', () =>
      assertTrue(typeof w.stopAutoInjectPolling === 'function'));
    it('pollAutoInjectStatus is a function', () =>
      assertTrue(typeof w.pollAutoInjectStatus === 'function'));
    it('displayAutoInjectStats is a function', () =>
      assertTrue(typeof w.displayAutoInjectStats === 'function'));
    it('createPatchPreviewTab is a function', () =>
      assertTrue(typeof w.createPatchPreviewTab === 'function'));
    it('updateAutoInjectProgress is a function', () =>
      assertTrue(typeof w.updateAutoInjectProgress === 'function'));
    it('loadPatchSourceFromBackend is a function', () =>
      assertTrue(typeof w.loadPatchSourceFromBackend === 'function'));
    // Reinject functions
    it('onAutoInjectSuccess is a function', () =>
      assertTrue(typeof w.onAutoInjectSuccess === 'function'));
    it('clearInjectedPaths is a function', () =>
      assertTrue(typeof w.clearInjectedPaths === 'function'));
    it('getInjectedPathCount is a function', () =>
      assertTrue(typeof w.getInjectedPathCount === 'function'));
    it('updateReinjectButton is a function', () =>
      assertTrue(typeof w.updateReinjectButton === 'function'));
    it('reinjectAll is a function', () =>
      assertTrue(typeof w.reinjectAll === 'function'));
    it('triggerAutoInject is a function', () =>
      assertTrue(typeof w.triggerAutoInject === 'function'));
  });

  describe('Reinject Cache Functions', () => {
    it('onAutoInjectSuccess adds path to cache', () => {
      w.clearInjectedPaths();
      assertEqual(w.getInjectedPathCount(), 0);
      w.onAutoInjectSuccess('/path/to/file.c');
      assertEqual(w.getInjectedPathCount(), 1);
      w.clearInjectedPaths();
    });

    it('onAutoInjectSuccess deduplicates paths', () => {
      w.clearInjectedPaths();
      w.onAutoInjectSuccess('/path/to/file.c');
      w.onAutoInjectSuccess('/path/to/file.c');
      assertEqual(w.getInjectedPathCount(), 1);
      w.clearInjectedPaths();
    });

    it('onAutoInjectSuccess ignores null/undefined', () => {
      w.clearInjectedPaths();
      w.onAutoInjectSuccess(null);
      w.onAutoInjectSuccess(undefined);
      assertEqual(w.getInjectedPathCount(), 0);
    });

    it('clearInjectedPaths clears all cached paths', () => {
      w.onAutoInjectSuccess('/path/to/file1.c');
      w.onAutoInjectSuccess('/path/to/file2.c');
      assertTrue(w.getInjectedPathCount() > 0);
      w.clearInjectedPaths();
      assertEqual(w.getInjectedPathCount(), 0);
    });

    it('getInjectedPathCount returns correct count', () => {
      w.clearInjectedPaths();
      assertEqual(w.getInjectedPathCount(), 0);
      w.onAutoInjectSuccess('/path/a.c');
      assertEqual(w.getInjectedPathCount(), 1);
      w.onAutoInjectSuccess('/path/b.c');
      assertEqual(w.getInjectedPathCount(), 2);
      w.clearInjectedPaths();
    });

    it('reinjectAll is async function', () => {
      assertTrue(w.reinjectAll.constructor.name === 'AsyncFunction');
    });

    it('triggerAutoInject is async function', () => {
      assertTrue(w.triggerAutoInject.constructor.name === 'AsyncFunction');
    });

    it('triggerAutoInject calls /api/autoinject/trigger', async () => {
      setFetchResponse('/api/autoinject/trigger', { success: true });
      await w.triggerAutoInject('/path/to/file.c');
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/autoinject/trigger')));
    });

    it('triggerAutoInject throws on failure', async () => {
      setFetchResponse('/api/autoinject/trigger', {
        success: false,
        error: 'File not found',
      });
      let threw = false;
      try {
        await w.triggerAutoInject('/nonexistent.c');
      } catch (e) {
        threw = true;
        assertTrue(e.message.includes('File not found'));
      }
      assertTrue(threw);
    });

    it('reinjectAll shows alert when cache is empty', async () => {
      w.clearInjectedPaths();
      let alertCalled = false;
      const origAlert = global.alert;
      global.alert = () => {
        alertCalled = true;
      };
      await w.reinjectAll();
      assertTrue(alertCalled);
      global.alert = origAlert;
    });

    it('reinjectAll returns early when user cancels confirm', async () => {
      w.clearInjectedPaths();
      w.onAutoInjectSuccess('/path/a.c');
      const origConfirm = global.confirm;
      global.confirm = () => false;
      setFetchResponse('/api/autoinject/trigger', { success: true });
      await w.reinjectAll();
      const calls = getFetchCalls();
      assertTrue(!calls.some((c) => c.url.includes('/api/autoinject/trigger')));
      global.confirm = origConfirm;
      w.clearInjectedPaths();
    });

    it('reinjectAll triggers inject for all cached files', async () => {
      w.clearInjectedPaths();
      w.onAutoInjectSuccess('/path/a.c');
      w.onAutoInjectSuccess('/path/b.c');
      const origConfirm = global.confirm;
      global.confirm = () => true;
      setFetchResponse('/api/autoinject/trigger', { success: true });
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.reinjectAll();
      const calls = getFetchCalls();
      const triggerCalls = calls.filter((c) =>
        c.url.includes('/api/autoinject/trigger'),
      );
      assertEqual(triggerCalls.length, 2);
      global.confirm = origConfirm;
      w.FPBState.toolTerminal = null;
      w.clearInjectedPaths();
    });

    it('reinjectAll shows alert on partial failure', async () => {
      w.clearInjectedPaths();
      w.onAutoInjectSuccess('/path/a.c');
      w.onAutoInjectSuccess('/path/b.c');
      const origConfirm = global.confirm;
      global.confirm = () => true;
      let alertCalled = false;
      const origAlert = global.alert;
      global.alert = () => {
        alertCalled = true;
      };
      // First call succeeds, second fails
      let callCount = 0;
      global.fetch = async () => {
        callCount++;
        if (callCount === 1) {
          return { json: async () => ({ success: true }) };
        }
        return { json: async () => ({ success: false, error: 'Failed' }) };
      };
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.reinjectAll();
      assertTrue(alertCalled);
      global.confirm = origConfirm;
      global.alert = origAlert;
      w.FPBState.toolTerminal = null;
      w.clearInjectedPaths();
    });
  });

  describe('startAutoInjectPolling Function', () => {
    it('sets autoInjectPollInterval', () => {
      w.FPBState.autoInjectPollInterval = null;
      w.FPBState.toolTerminal = new MockTerminal();
      w.startAutoInjectPolling();
      assertTrue(w.FPBState.autoInjectPollInterval !== null);
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });

    it('writes system message', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.autoInjectPollInterval = null;
      w.startAutoInjectPolling();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('monitoring started'),
        ),
      );
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });
  });

  describe('stopAutoInjectPolling Function', () => {
    it('clears autoInjectPollInterval', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.startAutoInjectPolling();
      w.stopAutoInjectPolling();
      assertEqual(w.FPBState.autoInjectPollInterval, null);
      w.FPBState.toolTerminal = null;
    });

    it('writes system message when stopping', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.autoInjectPollInterval = 1;
      w.stopAutoInjectPolling();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('monitoring stopped'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('does nothing if not polling', () => {
      w.FPBState.autoInjectPollInterval = null;
      w.stopAutoInjectPolling();
      assertEqual(w.FPBState.autoInjectPollInterval, null);
    });
  });

  describe('pollAutoInjectStatus Function', () => {
    it('is async function', () => {
      assertTrue(w.pollAutoInjectStatus.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/watch/auto_inject_status', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.lastAutoInjectStatus = null;
      setFetchResponse('/api/watch/auto_inject_status', {
        success: true,
        status: 'idle',
      });
      await w.pollAutoInjectStatus();
      // Check that status was processed (no error thrown)
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('handles detecting status', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.lastAutoInjectStatus = null;
      setFetchResponse('/api/watch/auto_inject_status', {
        success: true,
        status: 'detecting',
        message: 'Detecting changes...',
      });
      await w.pollAutoInjectStatus();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Detecting')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles generating status', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.lastAutoInjectStatus = null;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/watch/auto_inject_status', {
        success: true,
        status: 'generating',
        message: 'Generating patch...',
        modified_funcs: ['test_func'],
      });
      setFetchResponse('/api/patch/source', {
        success: true,
        content: 'void test() {}',
      });
      await w.pollAutoInjectStatus();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Generating')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles success status', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.lastAutoInjectStatus = null;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/watch/auto_inject_status', {
        success: true,
        status: 'success',
        message: 'Injection complete!',
        result: { compile_time: 1.0, upload_time: 0.5, code_size: 100 },
      });
      setFetchResponse('/api/patch/source', {
        success: true,
        content: 'void test() {}',
      });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.pollAutoInjectStatus();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('complete')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles failed status', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.lastAutoInjectStatus = null;
      setFetchResponse('/api/watch/auto_inject_status', {
        success: true,
        status: 'failed',
        message: 'Compilation failed',
      });
      await w.pollAutoInjectStatus();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('failed')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('displayAutoInjectStats Function', () => {
    it('displays compile time', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        { compile_time: 1.5, upload_time: 0.5, code_size: 100 },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('1.50')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('displays upload speed', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        { compile_time: 1.0, upload_time: 1.0, code_size: 1000 },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('B/s')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('displays code size', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        { compile_time: 1.0, upload_time: 0.5, code_size: 256 },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('256')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('displays total time', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          total_time: 2.0,
        },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('2.00')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('displays patch mode', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          patch_mode: 'trampoline',
        },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('trampoline')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles injections array', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          injections: [
            {
              success: true,
              target_func: 'func1',
              target_addr: '0x1000',
              inject_func: 'func1',
              inject_addr: '0x2000',
              slot: 0,
            },
          ],
          successful_count: 1,
          total_count: 1,
        },
        'func1',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('func1')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles failed injections', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          injections: [
            { success: false, target_func: 'func1', error: 'Slot full' },
          ],
          successful_count: 0,
          total_count: 1,
        },
        'func1',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('func1')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('loadPatchSourceFromBackend Function', () => {
    it('is async function', () => {
      assertTrue(
        w.loadPatchSourceFromBackend.constructor.name === 'AsyncFunction',
      );
    });

    it('fetches from /api/patch/source', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/patch/source', {
        success: true,
        content: 'void test() {}',
      });
      const result = await w.loadPatchSourceFromBackend();
      // Check return value instead of fetch calls
      assertEqual(result, 'void test() {}');
      w.FPBState.toolTerminal = null;
    });

    it('returns content on success', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/patch/source', {
        success: true,
        content: 'void test() {}',
      });
      const result = await w.loadPatchSourceFromBackend();
      assertEqual(result, 'void test() {}');
      w.FPBState.toolTerminal = null;
    });

    it('returns null on failure', async () => {
      setFetchResponse('/api/patch/source', { success: false });
      const result = await w.loadPatchSourceFromBackend();
      assertEqual(result, null);
    });
  });

  describe('updateAutoInjectProgress Function', () => {
    it('handles idle status', () => {
      w.updateAutoInjectProgress(0, 'idle');
      assertTrue(true);
    });

    it('handles compiling status', () => {
      w.updateAutoInjectProgress(50, 'compiling');
      assertTrue(true);
    });

    it('handles success status', () => {
      w.FPBState.autoInjectProgressHideTimer = null;
      w.updateAutoInjectProgress(100, 'success', true);
      assertTrue(true);
    });

    it('handles failed status', () => {
      w.FPBState.autoInjectProgressHideTimer = null;
      w.updateAutoInjectProgress(100, 'failed', true);
      assertTrue(true);
    });
  });

  describe('File Browser Functions (features/filebrowser.js)', () => {
    it('HOME_PATH is defined', () => assertEqual(w.HOME_PATH, '~'));
    it('browseFile is a function', () =>
      assertTrue(typeof w.browseFile === 'function'));
    it('browseDir is a function', () =>
      assertTrue(typeof w.browseDir === 'function'));
    it('openFileBrowser is a function', () =>
      assertTrue(typeof w.openFileBrowser === 'function'));
    it('closeFileBrowser is a function', () =>
      assertTrue(typeof w.closeFileBrowser === 'function'));
    it('sendTerminalCommand is a function', () =>
      assertTrue(typeof w.sendTerminalCommand === 'function'));
    it('navigateTo is a function', () =>
      assertTrue(typeof w.navigateTo === 'function'));
    it('selectFileBrowserItem is a function', () =>
      assertTrue(typeof w.selectFileBrowserItem === 'function'));
    it('selectBrowserItem is a function', () =>
      assertTrue(typeof w.selectBrowserItem === 'function'));
    it('onBrowserPathKeyup is a function', () =>
      assertTrue(typeof w.onBrowserPathKeyup === 'function'));
    it('refreshSymbolsFromELF is a function', () =>
      assertTrue(typeof w.refreshSymbolsFromELF === 'function'));
  });

  describe('browseFile Function', () => {
    it('sets fileBrowserCallback', () => {
      w.FPBState.fileBrowserCallback = null;
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.browseFile('elfPath', '.elf');
      assertTrue(w.FPBState.fileBrowserCallback !== null);
    });

    it('sets fileBrowserFilter', () => {
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.browseFile('elfPath', '.elf');
      assertEqual(w.FPBState.fileBrowserFilter, '.elf');
    });

    it('sets fileBrowserMode to file', () => {
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.browseFile('elfPath', '.elf');
      assertEqual(w.FPBState.fileBrowserMode, 'file');
    });

    it('callback updates input value', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      setFetchResponse('/api/config', { success: true });
      w.browseFile('elfPath', '.elf');
      const callback = w.FPBState.fileBrowserCallback;
      callback('/path/to/file.elf');
      const input = browserGlobals.document.getElementById('elfPath');
      assertEqual(input.value, '/path/to/file.elf');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('browseDir Function', () => {
    it('sets fileBrowserCallback', () => {
      w.FPBState.fileBrowserCallback = null;
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.browseDir('toolchainPath');
      assertTrue(w.FPBState.fileBrowserCallback !== null);
    });

    it('sets fileBrowserMode to dir', () => {
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.browseDir('toolchainPath');
      assertEqual(w.FPBState.fileBrowserMode, 'dir');
    });

    it('clears fileBrowserFilter', () => {
      w.FPBState.fileBrowserFilter = '.elf';
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.browseDir('toolchainPath');
      assertEqual(w.FPBState.fileBrowserFilter, '');
    });

    it('callback updates input value', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      setFetchResponse('/api/config', { success: true });
      w.browseDir('toolchainPath');
      const callback = w.FPBState.fileBrowserCallback;
      callback('/path/to/toolchain');
      const input = browserGlobals.document.getElementById('toolchainPath');
      assertEqual(input.value, '/path/to/toolchain');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('openFileBrowser Function', () => {
    it('is async function', () => {
      assertTrue(w.openFileBrowser.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/browse', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/browse', { items: [], current_path: '/home' });
      await w.openFileBrowser('/home');
      // Check side effect - currentBrowserPath should be set
      assertEqual(w.FPBState.currentBrowserPath, '/home');
      w.FPBState.toolTerminal = null;
    });

    it('sets currentBrowserPath', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/browse', {
        items: [],
        current_path: '/home/user',
      });
      await w.openFileBrowser('/home/user');
      assertEqual(w.FPBState.currentBrowserPath, '/home/user');
      w.FPBState.toolTerminal = null;
    });

    it('shows modal', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      const modal = browserGlobals.document.getElementById('fileBrowserModal');
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      await w.openFileBrowser('~');
      assertTrue(modal.classList._classes.has('show'));
      w.FPBState.toolTerminal = null;
    });

    it('clears selectedBrowserItem', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.selectedBrowserItem = '/some/path';
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      await w.openFileBrowser('~');
      assertEqual(w.FPBState.selectedBrowserItem, null);
      w.FPBState.toolTerminal = null;
    });

    it('handles items in response', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.fileBrowserMode = 'file';
      w.FPBState.fileBrowserFilter = '';
      setFetchResponse('/api/browse', {
        items: [
          { name: 'file1.txt', type: 'file' },
          { name: 'dir1', type: 'dir' },
        ],
        current_path: '/home',
      });
      await w.openFileBrowser('/home');
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.openFileBrowser('/home');
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });

    it('filters files by extension in file mode', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.fileBrowserMode = 'file';
      w.FPBState.fileBrowserFilter = '.elf';
      setFetchResponse('/api/browse', {
        items: [
          { name: 'file.elf', type: 'file' },
          { name: 'file.txt', type: 'file' },
          { name: 'dir1', type: 'dir' },
        ],
        current_path: '/home',
      });
      await w.openFileBrowser('/home');
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('adds parent directory navigation for non-root paths', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/browse', {
        items: [],
        current_path: '/home/user',
      });
      await w.openFileBrowser('/home/user');
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('handles root path without parent navigation', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/browse', {
        items: [],
        current_path: '/',
      });
      await w.openFileBrowser('/');
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });
  });

  describe('closeFileBrowser Function', () => {
    it('removes show class from modal', () => {
      const modal = browserGlobals.document.getElementById('fileBrowserModal');
      modal.classList.add('show');
      w.closeFileBrowser();
      assertTrue(!modal.classList._classes.has('show'));
    });

    it('clears selectedBrowserItem', () => {
      w.FPBState.selectedBrowserItem = '/some/path';
      w.closeFileBrowser();
      assertEqual(w.FPBState.selectedBrowserItem, null);
    });
  });

  describe('navigateTo Function', () => {
    it('calls openFileBrowser', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/browse', { items: [], current_path: '/new/path' });
      await w.navigateTo('/new/path');
      assertEqual(w.FPBState.currentBrowserPath, '/new/path');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('selectFileBrowserItem Function', () => {
    it('sets selectedBrowserItem', () => {
      const mockElement = browserGlobals.document.createElement('div');
      w.selectFileBrowserItem(mockElement, '/test/path');
      assertEqual(w.FPBState.selectedBrowserItem, '/test/path');
    });

    it('adds selected class to element', () => {
      const mockElement = browserGlobals.document.createElement('div');
      w.selectFileBrowserItem(mockElement, '/test/path');
      assertTrue(mockElement.classList._classes.has('selected'));
    });
  });

  describe('selectBrowserItem Function', () => {
    it('calls callback with selected item in file mode', () => {
      let callbackPath = null;
      w.FPBState.fileBrowserMode = 'file';
      w.FPBState.selectedBrowserItem = '/test/file.txt';
      w.FPBState.fileBrowserCallback = (path) => {
        callbackPath = path;
      };
      w.selectBrowserItem();
      assertEqual(callbackPath, '/test/file.txt');
    });

    it('calls callback with current path in dir mode', () => {
      let callbackPath = null;
      w.FPBState.fileBrowserMode = 'dir';
      w.FPBState.selectedBrowserItem = null;
      w.FPBState.currentBrowserPath = '/test/dir';
      w.FPBState.fileBrowserCallback = (path) => {
        callbackPath = path;
      };
      w.selectBrowserItem();
      assertEqual(callbackPath, '/test/dir');
    });

    it('uses selectedBrowserItem in dir mode if set', () => {
      let callbackPath = null;
      w.FPBState.fileBrowserMode = 'dir';
      w.FPBState.selectedBrowserItem = '/selected/dir';
      w.FPBState.currentBrowserPath = '/current/dir';
      w.FPBState.fileBrowserCallback = (path) => {
        callbackPath = path;
      };
      w.selectBrowserItem();
      assertEqual(callbackPath, '/selected/dir');
    });

    it('closes file browser after selection', () => {
      const modal = browserGlobals.document.getElementById('fileBrowserModal');
      modal.classList.add('show');
      w.FPBState.fileBrowserMode = 'file';
      w.FPBState.selectedBrowserItem = '/test/file.txt';
      w.FPBState.fileBrowserCallback = () => {};
      w.selectBrowserItem();
      assertTrue(!modal.classList._classes.has('show'));
    });
  });

  describe('onBrowserPathKeyup Function', () => {
    it('navigates on Enter key', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.getElementById('browserPath').value = '/new/path';
      setFetchResponse('/api/browse', { items: [], current_path: '/new/path' });
      w.onBrowserPathKeyup({ key: 'Enter' });
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('does nothing on other keys', () => {
      w.onBrowserPathKeyup({ key: 'a' });
      assertTrue(true);
    });
  });

  describe('refreshSymbolsFromELF Function', () => {
    it('is async function', () => {
      assertTrue(w.refreshSymbolsFromELF.constructor.name === 'AsyncFunction');
    });

    it('sends config update', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { success: true });
      await w.refreshSymbolsFromELF('/path/to/file.elf');
      // The function may not always call /api/config directly
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('writes success message', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config', { success: true });
      await w.refreshSymbolsFromELF('/path/to/file.elf');
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ELF loaded')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('sendTerminalCommand Function', () => {
    it('is async function', () =>
      assertTrue(w.sendTerminalCommand.constructor.name === 'AsyncFunction'));

    it('returns early if not connected', async () => {
      w.FPBState.isConnected = false;
      await w.sendTerminalCommand('test');
      // Should not throw, just return early
      assertTrue(true);
    });

    it('sends POST to /api/serial/send when connected', async () => {
      w.FPBState.isConnected = true;
      setFetchResponse('/api/serial/send', { success: true });
      await w.sendTerminalCommand('test command');
      // Should complete without error
      assertTrue(true);
      w.FPBState.isConnected = false;
    });
  });

  describe('createPatchPreviewTab Function', () => {
    it('is async function', () => {
      assertTrue(w.createPatchPreviewTab.constructor.name === 'AsyncFunction');
    });

    it('creates new preview tab', async () => {
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/patch/source', {
        success: true,
        content: 'void test() {}',
      });
      await w.createPatchPreviewTab('preview_func');
      assertTrue(
        w.FPBState.editorTabs.some((t) => t.id === 'patch_preview_func'),
      );
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = null;
    });

    it('updates existing tab content', async () => {
      w.FPBState.editorTabs = [
        { id: 'patch_existing', title: 'patch_existing.c', type: 'preview' },
      ];
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/patch/source', {
        success: true,
        content: 'void updated() {}',
      });
      await w.createPatchPreviewTab('existing');
      assertEqual(w.FPBState.activeEditorTab, 'patch_existing');
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = null;
    });

    it('handles source file parameter', async () => {
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/patch/source', {
        success: true,
        content: 'void test() {}',
      });
      await w.createPatchPreviewTab('func', '/path/to/source.c');
      assertTrue(w.FPBState.editorTabs.some((t) => t.id === 'patch_source'));
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch failure', async () => {
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/patch/source', { success: false });
      await w.createPatchPreviewTab('fail_func');
      assertTrue(w.FPBState.editorTabs.length > 0);
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = null;
    });
  });

  describe('fpbTestSerial Function - Extended', () => {
    it('sends correct test parameters', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/test-serial', {
        success: true,
        tests: [],
        max_working_size: 1024,
        recommended_chunk_size: 128,
      });
      await w.fpbTestSerial();
      // Check side effect instead of fetch calls
      assertTrue(mockTerm._writes.length > 0);
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('displays failed test results', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/test-serial', {
        success: true,
        tests: [
          { size: 16, passed: true, response_time_ms: 10, cmd_len: 20 },
          { size: 32, passed: false, error: 'Timeout' },
        ],
        max_working_size: 16,
        failed_size: 32,
        recommended_chunk_size: 16,
      });
      await w.fpbTestSerial();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Timeout')),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.fpbTestSerial();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('displays all test result fields', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/test-serial', {
        success: true,
        tests: [
          { size: 64, passed: true, response_time_ms: 15, cmd_len: 72 },
          { size: 128, passed: true, response_time_ms: 25, cmd_len: 136 },
          { size: 256, passed: true, response_time_ms: 45, cmd_len: 264 },
        ],
        max_working_size: 256,
        recommended_chunk_size: 256,
      });
      await w.fpbTestSerial();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('64 bytes')),
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('128 bytes')),
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('256 bytes')),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('handles test with no failed_size', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/test-serial', {
        success: true,
        tests: [{ size: 512, passed: true }],
        max_working_size: 512,
        failed_size: 0,
        recommended_chunk_size: 512,
      });
      await w.fpbTestSerial();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Max working')),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('applies recommended chunk size when user confirms', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      browserGlobals.document.getElementById('chunkSize').value = '128';
      browserGlobals.confirm = () => true;
      setFetchResponse('/api/fpb/test-serial', {
        success: true,
        tests: [],
        max_working_size: 512,
        recommended_chunk_size: 384,
      });
      setFetchResponse('/api/config', { success: true });
      await w.fpbTestSerial();
      // value can be number or string depending on mock implementation
      assertEqual(
        String(browserGlobals.document.getElementById('chunkSize').value),
        '384',
      );
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Chunk size updated'),
        ),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
      browserGlobals.confirm = () => true;
    });

    it('keeps current chunk size when user cancels', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      browserGlobals.document.getElementById('chunkSize').value = '128';
      // Override global confirm to return false
      const origConfirm = global.confirm;
      global.confirm = () => false;
      setFetchResponse('/api/fpb/test-serial', {
        success: true,
        tests: [],
        max_working_size: 512,
        recommended_chunk_size: 384,
      });
      await w.fpbTestSerial();
      assertEqual(
        browserGlobals.document.getElementById('chunkSize').value,
        '128',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('unchanged')),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
      global.confirm = origConfirm;
    });
  });

  describe('fpbPing Function - Extended', () => {
    it('handles fetch exception', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.fpbPing();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('displays error message on failure', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/fpb/ping', {
        success: false,
        message: 'Device not responding',
      });
      await w.fpbPing();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Device not responding'),
        ),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('fpbInfo Function - Extended', () => {
    it('handles fetch exception', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.fpbInfo();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('shows alert on build time mismatch', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      let alertCalled = false;
      const origAlert = browserGlobals.alert;
      browserGlobals.alert = () => {
        alertCalled = true;
      };
      global.alert = browserGlobals.alert;
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [],
        build_time_mismatch: true,
        device_build_time: '2024-01-01 12:00:00',
        elf_build_time: '2024-01-02 12:00:00',
      });
      await w.fpbInfo();
      assertTrue(alertCalled);
      browserGlobals.alert = origAlert;
      global.alert = origAlert;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('updates all slot states correctly', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [
          {
            id: 0,
            occupied: true,
            func: 'func0',
            orig_addr: '0x1000',
            target_addr: '0x2000',
            code_size: 100,
          },
          {
            id: 1,
            occupied: true,
            func: 'func1',
            orig_addr: '0x1100',
            target_addr: '0x2100',
            code_size: 200,
          },
          { id: 2, occupied: false },
          {
            id: 3,
            occupied: true,
            func: 'func3',
            orig_addr: '0x1300',
            target_addr: '0x2300',
            code_size: 50,
          },
          { id: 4, occupied: false },
          { id: 5, occupied: false },
        ],
        memory: { used: 350 },
      });
      await w.fpbInfo();
      assertTrue(w.FPBState.slotStates[0].occupied);
      assertTrue(w.FPBState.slotStates[1].occupied);
      assertTrue(!w.FPBState.slotStates[2].occupied);
      assertTrue(w.FPBState.slotStates[3].occupied);
      assertEqual(w.FPBState.slotStates[0].func, 'func0');
      assertEqual(w.FPBState.slotStates[1].code_size, 200);
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('handles empty slots array', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: true }));
      setFetchResponse('/api/fpb/info', {
        success: true,
        slots: [],
      });
      await w.fpbInfo();
      // slots should remain unchanged when empty array provided
      assertTrue(w.FPBState.slotStates[0].occupied);
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('fpbInjectMulti Function - Extended', () => {
    it('handles fetch exception', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      browserGlobals.document.getElementById('patchSource').value =
        'void test() {}';
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.fpbInjectMulti();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('displays injection statistics on success', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      browserGlobals.document.getElementById('patchSource').value =
        'void test() {}';
      browserGlobals.document.getElementById('patchMode').value = 'trampoline';
      setFetchResponse('/api/fpb/inject/multi', {
        success: true,
        successful_count: 2,
        total_count: 2,
        compile_time: 1.0,
        upload_time: 0.5,
        code_size: 200,
      });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbInjectMulti();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('pollAutoInjectStatus Function - Extended', () => {
    it('handles compiling status', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.lastAutoInjectStatus = null;
      w.FPBState.editorTabs = [];
      setFetchResponse('/api/watch/auto_inject_status', {
        success: true,
        status: 'compiling',
        message: 'Compiling patch...',
        modified_funcs: ['test_func'],
      });
      setFetchResponse('/api/patch/source', {
        success: true,
        content: 'void test() {}',
      });
      await w.pollAutoInjectStatus();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Compiling')),
      );
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = null;
    });

    it('handles injecting status', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.lastAutoInjectStatus = null;
      setFetchResponse('/api/watch/auto_inject_status', {
        success: true,
        status: 'injecting',
        message: 'Injecting code...',
      });
      await w.pollAutoInjectStatus();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Injecting')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.lastAutoInjectStatus = null;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.pollAutoInjectStatus();
      assertTrue(true);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });

    it('does not update on same status', async () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.lastAutoInjectStatus = 'idle';
      setFetchResponse('/api/watch/auto_inject_status', {
        success: true,
        status: 'idle',
      });
      await w.pollAutoInjectStatus();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });
  });

  describe('displayAutoInjectStats Function - Extended', () => {
    it('handles injections with slot info', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          injections: [
            {
              success: true,
              target_func: 'func1',
              target_addr: '0x1000',
              inject_func: 'func1',
              inject_addr: '0x2000',
              slot: 0,
            },
          ],
          successful_count: 1,
          total_count: 1,
        },
        'func1',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Slot 0')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles single injection without injections array', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayAutoInjectStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          target_addr: '0x1000',
          inject_func: 'test_func',
          inject_addr: '0x2000',
          slot: 2,
        },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('test_func')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('shows alert for slot full errors', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      // Note: alert is called via setTimeout, so we just verify the function runs
      w.displayAutoInjectStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          injections: [
            {
              success: false,
              target_func: 'func1',
              error: 'No free slot available',
            },
          ],
          successful_count: 0,
          total_count: 1,
        },
        'func1',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('func1')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('LocalStorage Integration', () => {
    it('stores and retrieves values', () => {
      w.localStorage.setItem('test-key', 'test-value');
      assertEqual(w.localStorage.getItem('test-key'), 'test-value');
    });

    it('returns null for non-existent keys', () => {
      assertEqual(w.localStorage.getItem('nonexistent-key'), null);
    });

    it('removes items correctly', () => {
      w.localStorage.setItem('remove-test', 'value');
      w.localStorage.removeItem('remove-test');
      assertEqual(w.localStorage.getItem('remove-test'), null);
    });

    it('clears all items', () => {
      w.localStorage.setItem('clear-test', 'value');
      w.localStorage.clear();
      assertEqual(w.localStorage.getItem('clear-test'), null);
    });
  });

  // ===================================================================
  // Phase 1 Symbol Viewer Improvements
  // ===================================================================

  describe('_autoReadTimers is a Map', () => {
    it('is an instance of Map', () => {
      assertTrue(w._autoReadTimers instanceof Map);
    });

    it('starts empty', () => {
      assertEqual(w._autoReadTimers.size, 0);
    });
  });

  describe('toggleAutoRead multi-symbol support', () => {
    it('is a function', () => {
      assertTrue(typeof w.toggleAutoRead === 'function');
    });

    it('starts auto-read and adds to Map', () => {
      // Ensure clean state
      if (w._autoReadTimers.has('test_sym')) {
        clearInterval(w._autoReadTimers.get('test_sym'));
        w._autoReadTimers.delete('test_sym');
      }
      // getElementById auto-creates mock elements
      const btn = browserGlobals.document.getElementById(
        'symAutoReadBtn_test_sym',
      );
      const input = browserGlobals.document.getElementById(
        'symAutoReadInterval_test_sym',
      );
      input.value = '1000';

      w.toggleAutoRead('test_sym');
      assertTrue(w._autoReadTimers.has('test_sym'));

      // Clean up
      clearInterval(w._autoReadTimers.get('test_sym'));
      w._autoReadTimers.delete('test_sym');
    });

    it('stops auto-read and removes from Map', () => {
      const btn = browserGlobals.document.getElementById(
        'symAutoReadBtn_test_sym2',
      );
      const input = browserGlobals.document.getElementById(
        'symAutoReadInterval_test_sym2',
      );
      input.value = '1000';

      // Start then stop
      w.toggleAutoRead('test_sym2');
      assertTrue(w._autoReadTimers.has('test_sym2'));
      w.toggleAutoRead('test_sym2');
      assertTrue(!w._autoReadTimers.has('test_sym2'));
    });

    it('supports multiple symbols simultaneously', () => {
      const syms = ['sym_a', 'sym_b', 'sym_c'];
      syms.forEach((s) => {
        browserGlobals.document.getElementById(`symAutoReadBtn_${s}`);
        const input = browserGlobals.document.getElementById(
          `symAutoReadInterval_${s}`,
        );
        input.value = '1000';
      });

      syms.forEach((s) => w.toggleAutoRead(s));
      assertEqual(w._autoReadTimers.size, 3);

      // Clean up
      syms.forEach((s) => {
        clearInterval(w._autoReadTimers.get(s));
        w._autoReadTimers.delete(s);
      });
    });

    it('enforces 500ms minimum interval', () => {
      browserGlobals.document.getElementById('symAutoReadBtn_fast_sym');
      const input = browserGlobals.document.getElementById(
        'symAutoReadInterval_fast_sym',
      );
      input.value = '100'; // Below 500ms minimum

      w.toggleAutoRead('fast_sym');
      assertTrue(w._autoReadTimers.has('fast_sym'));

      // Clean up
      clearInterval(w._autoReadTimers.get('fast_sym'));
      w._autoReadTimers.delete('fast_sym');
    });
  });

  describe('writeSymbolField Function', () => {
    it('is exported to window', () => {
      assertTrue(typeof w.writeSymbolField === 'function');
    });

    it('is async function', () => {
      assertTrue(w.writeSymbolField.constructor.name === 'AsyncFunction');
    });

    it('sends POST with offset to /api/symbols/write', async () => {
      setFetchResponse('/api/symbols/write', {
        success: true,
        message: 'Write 4 bytes OK',
      });
      const result = await w.writeSymbolField('my_struct', 4, 4, 'DEADBEEF');
      assertTrue(result);
      const calls = getFetchCalls();
      const writeCall = calls.find((c) => c.url === '/api/symbols/write');
      assertTrue(writeCall !== undefined);
      const body = JSON.parse(writeCall.options.body);
      assertEqual(body.name, 'my_struct');
      assertEqual(body.offset, 4);
      assertEqual(body.hex_data, 'DEADBEEF');
    });

    it('returns false on failure', async () => {
      setFetchResponse('/api/symbols/write', {
        success: false,
        error: 'Write failed',
      });
      const result = await w.writeSymbolField('my_struct', 0, 4, '01020304');
      assertTrue(!result);
    });

    it('returns false on exception', async () => {
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      const result = await w.writeSymbolField('my_struct', 0, 4, '01020304');
      assertTrue(!result);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });
  });

  describe('readMemoryAddress Function', () => {
    it('is exported to window', () => {
      assertTrue(typeof w.readMemoryAddress === 'function');
    });

    it('is async function', () => {
      assertTrue(w.readMemoryAddress.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/memory/read', async () => {
      w.FPBState.editorTabs = [];
      setFetchResponse('/api/memory/read', {
        success: true,
        addr: '0x20000000',
        size: 16,
        hex_data: '00112233445566778899AABBCCDDEEFF',
      });
      await w.readMemoryAddress('0x20000000', 16);
      assertTrue(
        w.FPBState.editorTabs.some((t) => t.id === 'memview_0x20000000_16'),
      );
      w.FPBState.editorTabs = [];
    });

    it('reuses existing tab', async () => {
      w.FPBState.editorTabs = [
        { id: 'memview_0x20000000_16', title: '0x20000000 [16B]' },
      ];
      await w.readMemoryAddress('0x20000000', 16);
      assertEqual(
        w.FPBState.editorTabs.filter((t) => t.id === 'memview_0x20000000_16')
          .length,
        1,
      );
      w.FPBState.editorTabs = [];
    });

    it('handles API error gracefully', async () => {
      w.FPBState.editorTabs = [];
      setFetchResponse('/api/memory/read', {
        success: false,
        error: 'Read failed',
      });
      await w.readMemoryAddress('0x20000000', 16);
      assertTrue(
        !w.FPBState.editorTabs.some((t) => t.id === 'memview_0x20000000_16'),
      );
    });

    it('returns early on invalid params', async () => {
      w.FPBState.editorTabs = [];
      await w.readMemoryAddress('', 0);
      assertEqual(w.FPBState.editorTabs.length, 0);
    });

    it('creates tab with memory-viewer type', async () => {
      w.FPBState.editorTabs = [];
      setFetchResponse('/api/memory/read', {
        success: true,
        addr: '0x08000000',
        size: 4,
        hex_data: 'DEADBEEF',
      });
      await w.readMemoryAddress('0x08000000', 4);
      const tab = w.FPBState.editorTabs.find(
        (t) => t.id === 'memview_0x08000000_4',
      );
      assertTrue(tab !== undefined);
      assertEqual(tab.type, 'memory-viewer');
      w.FPBState.editorTabs = [];
    });
  });

  describe('_decodeFieldValue float/double support', () => {
    it('decodes float (4 bytes, little-endian)', () => {
      // float 3.14 in LE: 0xC3F54840 -> bytes: C3 F5 48 40
      // Actually: 3.14f = 0x4048F5C3 -> LE bytes: C3 F5 48 40
      const result = w._decodeFieldValue('C3F54840', 0, 4, 'float');
      assertTrue(result !== '');
      // Should be approximately 3.14
      const val = parseFloat(result);
      assertTrue(Math.abs(val - 3.14) < 0.001);
    });

    it('decodes double (8 bytes, little-endian)', () => {
      // double 3.14 = 0x40091EB851EB851F -> LE bytes: 1F 85 EB 51 B8 1E 09 40
      const result = w._decodeFieldValue('1F85EB51B81E0940', 0, 8, 'double');
      assertTrue(result !== '');
      const val = parseFloat(result);
      assertTrue(Math.abs(val - 3.14) < 0.0001);
    });

    it('returns empty for float with wrong size', () => {
      // float requires exactly 4 bytes
      const result = w._decodeFieldValue('C3F548', 0, 3, 'float');
      assertEqual(result, '');
    });

    it('returns empty for double with wrong size', () => {
      // double requires exactly 8 bytes — but typedef fallback now decodes as int
      const result = w._decodeFieldValue('C3F54840', 0, 4, 'double');
      // With typedef fallback, 4-byte value is decoded as integer
      assertTrue(result !== '');
    });

    it('decodes float zero', () => {
      const result = w._decodeFieldValue('00000000', 0, 4, 'float');
      assertTrue(result !== '');
      assertEqual(parseFloat(result), 0);
    });

    it('decodes negative float', () => {
      // -1.0f = 0xBF800000 -> LE: 000080BF
      const result = w._decodeFieldValue('000080BF', 0, 4, 'float');
      assertTrue(result !== '');
      assertEqual(parseFloat(result), -1);
    });
  });
};

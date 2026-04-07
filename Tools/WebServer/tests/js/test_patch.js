/**
 * Tests for features/patch.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
  assertDeepEqual,
} = require('./framework');
const {
  resetMocks,
  setFetchResponse,
  getFetchCalls,
  browserGlobals,
  MockTerminal,
} = require('./mocks');

module.exports = function (w) {
  describe('Patch Functions (features/patch.js)', () => {
    it('generatePatchTemplate is a function', () =>
      assertTrue(typeof w.generatePatchTemplate === 'function'));
    it('formatCCode is a function', () =>
      assertTrue(typeof w.formatCCode === 'function'));
    it('processDecompiledCode is a function', () =>
      assertTrue(typeof w.processDecompiledCode === 'function'));
    it('parseSignature is a function', () =>
      assertTrue(typeof w.parseSignature === 'function'));
    it('extractParamNames is a function', () =>
      assertTrue(typeof w.extractParamNames === 'function'));
    it('performInject is a function', () =>
      assertTrue(typeof w.performInject === 'function'));
    it('displayInjectionStats is a function', () =>
      assertTrue(typeof w.displayInjectionStats === 'function'));
  });

  describe('formatCCode Function', () => {
    it('returns empty string for null input', () => {
      const result = w.formatCCode(null);
      assertEqual(result, '');
    });
    it('returns empty string for empty input', () => {
      const result = w.formatCCode('');
      assertEqual(result, '');
    });
    it('returns code as-is when js_beautify not available', () => {
      const code = 'int x = 0;';
      const result = w.formatCCode(code);
      assertTrue(result.includes('int x = 0'));
    });
  });

  describe('processDecompiledCode Function', () => {
    it('returns empty string for null input', () => {
      const result = w.processDecompiledCode(null);
      assertEqual(result, '');
    });
    it('returns empty string for empty input', () => {
      const result = w.processDecompiledCode('');
      assertEqual(result, '');
    });
    it('removes header comments', () => {
      const result = w.processDecompiledCode(
        '// Comment\n// Another\nvoid func() { return; }',
      );
      assertTrue(!result.includes('// Comment'));
    });
    it('replaces param_1 with first parameter name', () => {
      const result = w.processDecompiledCode(
        'void func(int param_1) { use(param_1); }',
        ['x'],
      );
      assertContains(result, 'x');
      assertTrue(!result.includes('param_1'));
    });
    it('replaces multiple param_N with parameter names', () => {
      const result = w.processDecompiledCode(
        'void func(int param_1, int param_2) { use(param_1, param_2); }',
        ['a', 'b'],
      );
      assertContains(result, 'a');
      assertContains(result, 'b');
      assertTrue(!result.includes('param_1'));
      assertTrue(!result.includes('param_2'));
    });
    it('extracts function body only', () => {
      const result = w.processDecompiledCode(
        'int test(int x) {\n  return x + 1;\n}',
      );
      /* Should not contain the function signature */
      assertTrue(!result.includes('int test('));
      assertContains(result, 'return');
    });
    it('preserves Ghidra types as-is', () => {
      const result = w.processDecompiledCode(
        'void func() { uint x = 0; ushort y = 1; }',
      );
      assertContains(result, 'uint');
      assertContains(result, 'ushort');
    });
    it('preserves DAT_ symbols as-is', () => {
      const result = w.processDecompiledCode(
        'void func() { int x = DAT_08007e08; }',
      );
      assertContains(result, 'DAT_08007e08');
    });
  });

  describe('parseSignature Function', () => {
    it('extracts return type and params', () => {
      const result = w.parseSignature(
        'int main(int argc, char **argv)',
        'main',
      );
      assertEqual(result.returnType, 'int');
      assertEqual(result.params, 'int argc, char **argv');
    });
    it('handles void return', () => {
      const result = w.parseSignature('void setup(void)', 'setup');
      assertEqual(result.returnType, 'void');
      assertEqual(result.params, '');
    });
    it('handles pointer return types', () => {
      const result = w.parseSignature('char *get_string(int id)', 'get_string');
      assertEqual(result.returnType, 'char *');
    });
    it('handles static functions', () => {
      const result = w.parseSignature('static int helper(int x)', 'helper');
      assertEqual(result.returnType, 'int');
      assertEqual(result.params, 'int x');
    });
    it('handles inline functions', () => {
      const result = w.parseSignature('inline void fast_op(void)', 'fast_op');
      assertEqual(result.returnType, 'void');
      assertEqual(result.params, '');
    });
    it('handles const return types', () => {
      const result = w.parseSignature('const char *get_name(void)', 'get_name');
      assertContains(result.returnType, 'char');
    });
    it('handles unsigned types', () => {
      const result = w.parseSignature(
        'unsigned int get_count(void)',
        'get_count',
      );
      assertContains(result.returnType, 'unsigned');
    });
    it('handles long long types', () => {
      const result = w.parseSignature('long long get_time(void)', 'get_time');
      assertContains(result.returnType, 'long');
    });
    it('handles struct return types', () => {
      const result = w.parseSignature('struct point get_pos(void)', 'get_pos');
      assertContains(result.returnType, 'struct');
    });
    it('handles no params', () => {
      const result = w.parseSignature('int get_value()', 'get_value');
      assertEqual(result.returnType, 'int');
    });
    it('handles extern functions', () => {
      const result = w.parseSignature('extern int ext_func(int x)', 'ext_func');
      assertEqual(result.returnType, 'int');
    });
    it('handles volatile return', () => {
      const result = w.parseSignature('volatile int get_reg(void)', 'get_reg');
      assertContains(result.returnType, 'int');
    });
    it('handles multiple modifiers', () => {
      const result = w.parseSignature(
        'static inline int fast_func(int x)',
        'fast_func',
      );
      assertEqual(result.returnType, 'int');
    });
    it('handles double pointer return', () => {
      const result = w.parseSignature(
        'char **get_strings(void)',
        'get_strings',
      );
      assertContains(result.returnType, 'char');
    });
  });

  describe('extractParamNames Function', () => {
    it('extracts simple params', () => {
      const names = w.extractParamNames('int x, int y');
      assertDeepEqual(names, ['x', 'y']);
    });
    it('handles pointers', () => {
      const names = w.extractParamNames('char *str, int *ptr');
      assertDeepEqual(names, ['str', 'ptr']);
    });
    it('handles arrays', () => {
      const names = w.extractParamNames('int arr[], char buf[256]');
      assertDeepEqual(names, ['arr', 'buf']);
    });
    it('returns empty for void', () => {
      const names = w.extractParamNames('void');
      assertDeepEqual(names, []);
    });
    it('returns empty for empty string', () => {
      const names = w.extractParamNames('');
      assertDeepEqual(names, []);
    });
    it('handles function pointers', () => {
      const names = w.extractParamNames('void (*callback)(int)');
      assertDeepEqual(names, ['callback']);
    });
    it('handles double pointers', () => {
      const names = w.extractParamNames('char **argv');
      assertDeepEqual(names, ['argv']);
    });
    it('handles const params', () => {
      const names = w.extractParamNames('const char *str');
      assertDeepEqual(names, ['str']);
    });
    it('handles struct params', () => {
      const names = w.extractParamNames('struct point p');
      assertDeepEqual(names, ['p']);
    });
    it('handles multiple complex params', () => {
      const names = w.extractParamNames('int a, char *b, float c');
      assertDeepEqual(names, ['a', 'b', 'c']);
    });
    it('handles nested parentheses', () => {
      const names = w.extractParamNames('int (*fn)(int, int), int x');
      assertTrue(names.includes('fn'));
      assertTrue(names.includes('x'));
    });
    it('handles unsigned params', () => {
      const names = w.extractParamNames('unsigned int count');
      assertDeepEqual(names, ['count']);
    });
    it('handles reference params', () => {
      const names = w.extractParamNames('int &ref');
      assertDeepEqual(names, ['ref']);
    });
    it('handles whitespace variations', () => {
      const names = w.extractParamNames('int   x  ,  int   y');
      assertDeepEqual(names, ['x', 'y']);
    });
    it('handles single param', () => {
      const names = w.extractParamNames('int x');
      assertDeepEqual(names, ['x']);
    });
    it('handles long type names', () => {
      const names = w.extractParamNames('unsigned long long value');
      assertDeepEqual(names, ['value']);
    });
    it('handles enum params', () => {
      const names = w.extractParamNames('enum color c');
      assertDeepEqual(names, ['c']);
    });
    it('handles union params', () => {
      const names = w.extractParamNames('union data d');
      assertDeepEqual(names, ['d']);
    });
  });

  describe('generatePatchTemplate Function', () => {
    it('generates template with function name', () => {
      const template = w.generatePatchTemplate('test_func', 0);
      assertContains(template, 'test_func');
      assertContains(template, 'FPB_INJECT');
    });
    it('uses signature params in function definition', () => {
      const template = w.generatePatchTemplate(
        'my_func',
        1,
        'int my_func(int x)',
      );
      /* Signature is used to generate function definition */
      assertContains(template, 'int my_func(int x)');
      assertContains(template, '__attribute__');
    });
    it('includes source file when provided', () => {
      const template = w.generatePatchTemplate('func', 0, null, 'main.c');
      assertContains(template, 'main.c');
    });
    it('includes decompiled code when provided', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        null,
        null,
        'void func() { int x = 0;\nreturn; }',
      );
      assertContains(template, 'DECOMPILED REFERENCE');
      assertContains(template, '#if 0');
      assertContains(template, '#endif');
    });
    it('decompiled code is inside function body', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        null,
        null,
        'void func() { int x = 0;\nreturn; }',
      );
      /* Check that #if 0 appears after the function opening brace */
      const funcStart = template.indexOf('func(');
      const bracePos = template.indexOf('{', funcStart);
      const ifZeroPos = template.indexOf('#if 0');
      assertTrue(
        ifZeroPos > bracePos,
        'Decompiled code should be inside function body',
      );
    });
    it('filters out header comments from decompiled code', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        null,
        null,
        '// Decompiled from: test.elf\n// Function: func\nvoid func() { int x = 0; }',
      );
      /* Header comments should be filtered out */
      assertTrue(!template.includes('Decompiled from: test.elf'));
    });
    it('replaces param_N with actual parameter names', () => {
      const template = w.generatePatchTemplate(
        'digitalWrite',
        0,
        'void digitalWrite(uint8_t pin, uint8_t value)',
        null,
        'void digitalWrite(int param_1, int param_2) {\n  if (param_1 > 0) {\n    use(param_2);\n  }\n}',
      );
      /* param_1 should be replaced with pin, param_2 with value */
      assertContains(template, 'pin');
      assertContains(template, 'value');
      assertTrue(!template.includes('param_1'));
      assertTrue(!template.includes('param_2'));
    });
    it('extracts function body only from decompiled code', () => {
      const template = w.generatePatchTemplate(
        'test',
        0,
        'int test(int x)',
        null,
        'int test(int param_1) {\n  return param_1 + 1;\n}',
      );
      /* Should not have duplicate function definition inside #if 0 */
      const ifZeroStart = template.indexOf('#if 0');
      const endifPos = template.indexOf('#endif');
      const decompiledSection = template.substring(ifZeroStart, endifPos);
      /* The decompiled section should not contain the full function signature */
      assertTrue(!decompiledSection.includes('int test(int'));
    });
    it('skips fl_println when decompiled code is provided', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        'void func(void)',
        null,
        'void func() { return; }',
      );
      /* Should not have fl_println when decompiled code is present */
      assertTrue(!template.includes('fl_println'));
    });
    it('includes fl_println when no decompiled code', () => {
      const template = w.generatePatchTemplate('func', 0);
      /* Should have fl_println when no decompiled code */
      assertContains(template, 'fl_println');
    });
    it('uses block comments style consistently', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        'void func(void)',
        null,
        'void func() { return; }',
      );
      /* Should use block comments, not line comments */
      assertTrue(!template.includes('// '));
      assertContains(template, '/*');
      assertContains(template, '*/');
    });
    it('includes Ghidra tip when not configured', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        null,
        null,
        null,
        true,
      );
      assertContains(template, 'Ghidra');
    });
    it('generates return statement for non-void', () => {
      const template = w.generatePatchTemplate(
        'get_val',
        0,
        'int get_val(void)',
      );
      assertContains(template, 'return');
    });
    it('indicates original function cannot be called for void', () => {
      const template = w.generatePatchTemplate(
        'do_thing',
        0,
        'void do_thing(void)',
      );
      /* Should have TODO comment */
      assertContains(template, 'TODO');
    });
    it('includes param names in function', () => {
      const template = w.generatePatchTemplate(
        'add',
        0,
        'int add(int a, int b)',
      );
      assertContains(template, 'int a');
      assertContains(template, 'int b');
    });
    it('handles complex signatures', () => {
      const template = w.generatePatchTemplate(
        'process',
        0,
        'void process(char *buf, int len)',
      );
      assertContains(template, 'char *buf');
      assertContains(template, 'int len');
    });
    it('includes standard headers', () => {
      const template = w.generatePatchTemplate('func', 0);
      assertContains(template, '#include <stdbool.h>');
      assertContains(template, '#include <stdint.h>');
      assertContains(template, '#include <stdio.h>');
    });
    it('includes fl_println debug message', () => {
      const template = w.generatePatchTemplate('my_func', 0);
      assertContains(template, 'fl_println');
      assertContains(template, 'Patched');
    });
    it('handles slot number in template', () => {
      const template = w.generatePatchTemplate('func', 5);
      /* Slot number should not appear in template (uses FPB_PATCH_COMP_ID macro) */
      assertTrue(!template.includes('Slot: 5'));
    });
    it('handles void params', () => {
      const template = w.generatePatchTemplate('init', 0, 'void init(void)');
      assertContains(template, 'FPB_INJECT');
      assertContains(template, 'void init');
    });
    it('handles pointer return with params', () => {
      const template = w.generatePatchTemplate(
        'alloc',
        0,
        'void *alloc(int size)',
      );
      assertContains(template, 'int size');
    });
    /* Tests for origAddr parameter - call original function pattern */
    it('generates call-original pattern when origAddr provided', () => {
      const template = w.generatePatchTemplate(
        'test_func',
        0,
        'void test_func(int x)',
        null,
        null,
        false,
        '0x08001234',
      );
      assertContains(template, 'ORIG_TEST_FUNC');
      assertContains(template, 'fpb_enable_patch');
      assertContains(template, '0x08001234');
    });
    it('generates function pointer typedef with origAddr', () => {
      const template = w.generatePatchTemplate(
        'my_func',
        1,
        'int my_func(int a, int b)',
        null,
        null,
        false,
        '0x08002000',
      );
      assertContains(template, 'typedef');
      assertContains(template, 'my_func_fn_t');
      assertContains(template, 'ORIG_MY_FUNC');
    });
    it('generates correct call pattern for void function', () => {
      const template = w.generatePatchTemplate(
        'do_work',
        2,
        'void do_work(int val)',
        null,
        null,
        false,
        '0x08003000',
      );
      assertContains(template, 'fpb_enable_patch(FPB_PATCH_COMP_ID, false)');
      assertContains(template, 'ORIG_DO_WORK(val)');
      assertContains(template, 'fpb_enable_patch(FPB_PATCH_COMP_ID, true)');
      /* void function should not have result variable */
      assertTrue(!template.includes('result ='));
    });
    it('generates correct call pattern for non-void function', () => {
      const template = w.generatePatchTemplate(
        'get_value',
        3,
        'int get_value(void)',
        null,
        null,
        false,
        '0x08004000',
      );
      assertContains(template, 'int result = ORIG_GET_VALUE()');
      assertContains(template, 'return result');
    });
    it('includes fpb_enable_patch when origAddr provided', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        null,
        null,
        null,
        false,
        '0x08001000',
      );
      assertContains(template, 'fpb_enable_patch');
    });
    it('shows Original address in header comment', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        null,
        null,
        null,
        false,
        '0x08005000',
      );
      assertContains(template, 'Original: 0x08005000');
    });
    it('sets Thumb bit (| 1) for ARM Cortex-M', () => {
      const template = w.generatePatchTemplate(
        'func',
        0,
        'void func(void)',
        null,
        null,
        false,
        '0x08001234',
      );
      /* Address should have | 1 for Thumb mode */
      assertContains(template, '0x08001234 | 1');
      assertContains(template, 'Thumb bit');
    });
    it('uses FPB_PATCH_COMP_ID macro instead of hardcoded slot', () => {
      const template = w.generatePatchTemplate(
        'func',
        3,
        'void func(void)',
        null,
        null,
        false,
        '0x08001000',
      );
      assertContains(template, 'FPB_PATCH_COMP_ID');
      /* Should NOT contain hardcoded slot number in fpb_enable_patch */
      assertTrue(!template.includes('fpb_enable_patch(3,'));
    });
    it('does not include Slot line in header comment', () => {
      const template = w.generatePatchTemplate('func', 2);
      assertTrue(!template.includes('Slot:'));
    });
    it('uses static const for function pointer', () => {
      const template = w.generatePatchTemplate(
        'test',
        0,
        'void test(void)',
        null,
        null,
        false,
        '0x08002000',
      );
      /* Should use static const, not #define */
      assertContains(template, 'static');
      assertContains(template, 'const');
      assertTrue(!template.includes('#define ORIG_'));
    });
  });

  describe('displayInjectionStats Function', () => {
    it('is a function', () => {
      assertTrue(typeof w.displayInjectionStats === 'function');
    });

    it('displays compile time', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayInjectionStats(
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
      w.displayInjectionStats(
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
      w.displayInjectionStats(
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
      w.displayInjectionStats(
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
      browserGlobals.document.getElementById('patchMode').value = 'trampoline';
      w.displayInjectionStats(
        { compile_time: 1.0, upload_time: 0.5, code_size: 100 },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('trampoline')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('displays target address', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayInjectionStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          target_addr: '0x08001000',
        },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('0x08001000')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('displays inject function address', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayInjectionStats(
        {
          compile_time: 1.0,
          upload_time: 0.5,
          code_size: 100,
          inject_func: 'test_func',
          inject_addr: '0x20000100',
        },
        'test_func',
      );
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('test_func')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles zero upload time', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayInjectionStats(
        { compile_time: 1.0, upload_time: 0, code_size: 100 },
        'test_func',
      );
      assertTrue(mockTerm._writes.length > 0);
      w.FPBState.toolTerminal = null;
    });

    it('handles missing optional fields', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.displayInjectionStats({}, 'test_func');
      assertTrue(mockTerm._writes.length > 0);
      w.FPBState.toolTerminal = null;
    });
  });

  describe('performInject Function', () => {
    it('is async function', () => {
      assertTrue(w.performInject.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.performInject();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('returns error if all slots occupied', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: true, func: 'test' }));
      browserGlobals.confirm = () => false;
      await w.performInject();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('slots are occupied'),
        ),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
      browserGlobals.confirm = () => true;
    });

    it('returns error if no patch tab selected', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.FPBState.currentPatchTab = null;
      await w.performInject();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('No patch tab'),
        ),
      );
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('returns error if no source code', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.FPBState.currentPatchTab = { id: 'patch_test', funcName: 'test_func' };
      w.FPBState.aceEditors.set('patch_test', { getValue: () => '   ' });
      await w.performInject();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('No patch source code'),
        ),
      );
      w.FPBState.aceEditors.delete('patch_test');
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('prompts for overwrite if slot occupied', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.selectedSlot = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map((_, i) => ({
          occupied: i === 0,
          func: i === 0 ? 'old_func' : '',
        }));
      w.FPBState.currentPatchTab = { id: 'patch_test', funcName: 'test_func' };
      w.FPBState.aceEditors.set('patch_test', {
        getValue: () => 'void test() {}',
      });
      const origConfirm = global.confirm;
      global.confirm = () => false;
      await w.performInject();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('cancelled')),
      );
      w.FPBState.aceEditors.delete('patch_test');
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
      global.confirm = origConfirm;
    });

    it('sends POST to /api/fpb/inject/stream', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.selectedSlot = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.FPBState.currentPatchTab = { id: 'patch_test', funcName: 'test_func' };
      w.FPBState.aceEditors.set('patch_test', {
        getValue: () => 'void test() {}',
      });
      browserGlobals.document.getElementById('patchMode').value = 'trampoline';
      setFetchResponse('/api/fpb/inject/stream', {
        _stream: [
          'data: {"type":"status","stage":"compiling"}\n',
          'data: {"type":"progress","percent":50,"uploaded":50,"total":100}\n',
          'data: {"type":"result","success":true,"compile_time":1.0,"upload_time":0.5,"code_size":100}\n',
        ],
      });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.performInject();
      // Should have written success message
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );
      w.FPBState.aceEditors.delete('patch_test');
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('sends comp -1 in auto slot mode', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.selectedSlot = -1;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.FPBState.currentPatchTab = { id: 'patch_test', funcName: 'test_func' };
      w.FPBState.aceEditors.set('patch_test', {
        getValue: () => 'void test() {}',
      });
      browserGlobals.document.getElementById('patchMode').value = 'trampoline';
      setFetchResponse('/api/fpb/inject/stream', {
        _stream: [
          'data: {"type":"result","success":true,"compile_time":1.0,"upload_time":0.5,"code_size":100}\n',
        ],
      });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.performInject();
      /* Verify the fetch body contains comp: -1 */
      const calls = getFetchCalls();
      const injectCall = calls.find((c) =>
        c.url.includes('/api/fpb/inject/stream'),
      );
      assertTrue(injectCall !== undefined, 'Should call inject/stream API');
      if (injectCall && injectCall.options && injectCall.options.body) {
        const body = JSON.parse(injectCall.options.body);
        assertEqual(body.comp, -1);
      }
      w.FPBState.aceEditors.delete('patch_test');
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('skips slot-occupied check in auto mode', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.selectedSlot = -1;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map((_, i) => ({
          occupied: i === 0,
          func: i === 0 ? 'old_func' : '',
        }));
      w.FPBState.currentPatchTab = { id: 'patch_test', funcName: 'test_func' };
      w.FPBState.aceEditors.set('patch_test', {
        getValue: () => 'void test() {}',
      });
      browserGlobals.document.getElementById('patchMode').value = 'trampoline';
      setFetchResponse('/api/fpb/inject/stream', {
        _stream: [
          'data: {"type":"result","success":true,"compile_time":1.0,"upload_time":0.5,"code_size":100}\n',
        ],
      });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      /* Should NOT prompt for overwrite in auto mode */
      const origConfirm = global.confirm;
      let confirmCalled = false;
      global.confirm = () => {
        confirmCalled = true;
        return false;
      };
      await w.performInject();
      assertTrue(
        !confirmCalled,
        'Should not prompt for overwrite in auto mode',
      );
      w.FPBState.aceEditors.delete('patch_test');
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
      global.confirm = origConfirm;
    });

    it('handles injection failure', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.selectedSlot = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.FPBState.currentPatchTab = { id: 'patch_test', funcName: 'test_func' };
      w.FPBState.aceEditors.set('patch_test', {
        getValue: () => 'void test() {}',
      });
      setFetchResponse('/api/fpb/inject/stream', {
        _stream: [
          'data: {"type":"result","success":false,"error":"Compilation failed"}\n',
        ],
      });
      await w.performInject();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Compilation failed'),
        ),
      );
      w.FPBState.aceEditors.delete('patch_test');
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
  });
};

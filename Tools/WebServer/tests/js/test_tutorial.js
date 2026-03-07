/**
 * Tests for features/tutorial.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertFalse,
} = require('./framework');
const {
  browserGlobals,
  resetMocks,
  setFetchResponse,
  getFetchCalls,
  createMockElement,
  getElement,
  mockElements,
} = require('./mocks');

module.exports = function (w) {
  // Helper: clear tutorial localStorage
  function clearTutorialStorage() {
    browserGlobals.window.localStorage.removeItem(
      'fpbinject_tutorial_completed',
    );
  }

  // Helper: create all tutorial DOM elements
  function setupTutorialDOM() {
    createMockElement('tutorialOverlay');
    createMockElement('tutorialBody');
    createMockElement('tutorialTitle');
    createMockElement('tutorialStepCount');
    createMockElement('tutorialProgress');
    createMockElement('tutorialPrevBtn');
    createMockElement('tutorialSkipBtn');
    createMockElement('tutorialNextBtn');
    createMockElement('tutorialSkipAllBtn');
    // Add tutorial-modal for positionModalNearTarget coverage
    const modal = createMockElement('tutorial-modal');
    modal.classList.add('tutorial-modal');
    mockElements['tutorial-modal'] = modal;
    // Add highlight targets for positioning coverage
    const panel = createMockElement('panelContainer');
    mockElements['panelContainer'] = panel;
    const editor = createMockElement('editorContainer');
    mockElements['editorContainer'] = editor;
  }

  /* ===========================
     FUNCTION EXPORTS
     =========================== */

  describe('Tutorial - Function Exports', () => {
    it('shouldShowTutorial is a function', () =>
      assertTrue(typeof w.shouldShowTutorial === 'function'));
    it('startTutorial is a function', () =>
      assertTrue(typeof w.startTutorial === 'function'));
    it('tutorialNext is a function', () =>
      assertTrue(typeof w.tutorialNext === 'function'));
    it('tutorialPrev is a function', () =>
      assertTrue(typeof w.tutorialPrev === 'function'));
    it('tutorialSkip is a function', () =>
      assertTrue(typeof w.tutorialSkip === 'function'));
    it('tutorialSkipAll is a function', () =>
      assertTrue(typeof w.tutorialSkipAll === 'function'));
    it('tutorialGoTo is a function', () =>
      assertTrue(typeof w.tutorialGoTo === 'function'));
    it('finishTutorial is a function', () =>
      assertTrue(typeof w.finishTutorial === 'function'));
    it('renderTutorialStep is a function', () =>
      assertTrue(typeof w.renderTutorialStep === 'function'));
  });

  /* ===========================
     shouldShowTutorial
     =========================== */

  describe('Tutorial - shouldShowTutorial', () => {
    it('returns true when first_launch=true and no localStorage', () => {
      clearTutorialStorage();
      const result = w.shouldShowTutorial({ first_launch: true });
      assertTrue(result === true);
    });

    it('returns false when first_launch=false', () => {
      clearTutorialStorage();
      const result = w.shouldShowTutorial({ first_launch: false });
      assertFalse(result);
    });

    it('returns false when configData is null', () => {
      clearTutorialStorage();
      const result = w.shouldShowTutorial(null);
      assertFalse(result);
    });

    it('returns false when configData is undefined', () => {
      clearTutorialStorage();
      const result = w.shouldShowTutorial(undefined);
      assertFalse(result);
    });

    it('returns true and clears stale localStorage when first_launch=true', () => {
      browserGlobals.window.localStorage.setItem(
        'fpbinject_tutorial_completed',
        'true',
      );
      const result = w.shouldShowTutorial({ first_launch: true });
      assertTrue(result);
      // localStorage should have been cleared
      assertEqual(
        browserGlobals.window.localStorage.getItem(
          'fpbinject_tutorial_completed',
        ),
        null,
      );
      clearTutorialStorage();
    });

    it('returns false when first_launch is missing', () => {
      clearTutorialStorage();
      const result = w.shouldShowTutorial({});
      assertFalse(result);
    });
  });

  /* ===========================
     startTutorial / finishTutorial
     =========================== */

  describe('Tutorial - Lifecycle', () => {
    it('startTutorial shows overlay', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      const overlay = getElement('tutorialOverlay');
      assertTrue(overlay.classList.contains('show'));
    });

    it('finishTutorial removes overlay show class', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.finishTutorial();
      const overlay = getElement('tutorialOverlay');
      assertFalse(overlay.classList.contains('show'));
    });

    it('finishTutorial sets localStorage', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.finishTutorial();
      assertEqual(
        browserGlobals.window.localStorage.getItem(
          'fpbinject_tutorial_completed',
        ),
        'true',
      );
      clearTutorialStorage();
    });

    it('shouldShowTutorial returns false after finishTutorial with first_launch=false', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.finishTutorial();
      // Normal case: after finishing, server sets first_launch=false
      assertFalse(w.shouldShowTutorial({ first_launch: false }));
      clearTutorialStorage();
    });
  });

  /* ===========================
     STEP NAVIGATION
     =========================== */

  // Helper: count active dot index from progress innerHTML
  function getActiveDotIndex() {
    const progress = getElement('tutorialProgress');
    const html = progress.innerHTML;
    const dots = html.match(/tutorial-dot[^"]*/g) || [];
    for (let i = 0; i < dots.length; i++) {
      if (dots[i].includes('active')) return i;
    }
    return -1;
  }

  describe('Tutorial - Step Navigation', () => {
    it('tutorialNext advances step', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      w.tutorialNext(); // step 1
      assertEqual(getActiveDotIndex(), 1);
    });

    it('tutorialPrev goes back', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      w.tutorialNext(); // step 1
      w.tutorialPrev(); // step 0
      assertEqual(getActiveDotIndex(), 0);
    });

    it('tutorialPrev does nothing at step 0', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      w.tutorialPrev(); // still step 0
      assertEqual(getActiveDotIndex(), 0);
    });

    it('tutorialSkip advances step like next', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      w.tutorialSkip(); // step 1
      assertEqual(getActiveDotIndex(), 1);
    });

    it('tutorialGoTo jumps to specific step', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      w.tutorialGoTo(3); // step 3
      assertEqual(getActiveDotIndex(), 3);
    });

    it('tutorialGoTo ignores negative index', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      w.tutorialGoTo(-1); // should stay at 0
      assertEqual(getActiveDotIndex(), 0);
    });

    it('tutorialGoTo ignores out-of-range index', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      w.tutorialGoTo(999); // should stay at 0
      assertEqual(getActiveDotIndex(), 0);
    });
  });

  /* ===========================
     SKIP ALL
     =========================== */

  describe('Tutorial - Skip All', () => {
    it('tutorialSkipAll finishes tutorial immediately', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialSkipAll();
      const overlay = getElement('tutorialOverlay');
      assertFalse(overlay.classList.contains('show'));
      assertEqual(
        browserGlobals.window.localStorage.getItem(
          'fpbinject_tutorial_completed',
        ),
        'true',
      );
      clearTutorialStorage();
    });
  });

  /* ===========================
     STEP RENDERING
     =========================== */

  describe('Tutorial - Step Rendering', () => {
    it('welcome step renders icon', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0 = welcome
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('🔧'));
    });

    it('connection step renders feature list', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(2); // connection
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-list'));
    });

    it('quickcmd step renders feature list', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(4); // quickcmd
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-list'));
    });

    it('complete step renders summary', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(13); // complete
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-summary'));
    });

    it('complete step shows 🎉 icon', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(13); // complete
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('🎉'));
    });

    it('prev button hidden on first step', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      const prevBtn = getElement('tutorialPrevBtn');
      assertEqual(prevBtn.style.display, 'none');
    });

    it('prev button visible on step > 0', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialNext(); // step 1
      const prevBtn = getElement('tutorialPrevBtn');
      assertTrue(prevBtn.style.display !== 'none');
    });

    it('skip button hidden on last step', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(13); // last step
      const skipBtn = getElement('tutorialSkipBtn');
      assertEqual(skipBtn.style.display, 'none');
    });

    it('skipAll button hidden on last step', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(13); // last step
      const skipAllBtn = getElement('tutorialSkipAllBtn');
      assertEqual(skipAllBtn.style.display, 'none');
    });

    it('progress dots rendered for all steps', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      const progress = getElement('tutorialProgress');
      // 14 steps = 14 dot buttons
      const dotCount = (progress.innerHTML.match(/tutorial-dot/g) || []).length;
      assertEqual(dotCount, 14);
    });
  });

  /* ===========================
     CONFIGURED TRACKING
     =========================== */

  describe('Tutorial - Configured Tracking', () => {
    it('tutorialNext marks current step as configured', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0 = welcome
      w.tutorialNext(); // marks welcome, moves to step 1 = appearance
      w.tutorialNext(); // marks appearance as configured, moves to step 2
      // Go to complete step to check summary - appearance should be configured
      w.tutorialGoTo(13);
      const body = getElement('tutorialBody');
      // connection was marked configured via tutorialNext (welcome is excluded from summary)
      assertTrue(body.innerHTML.includes('configured'));
    });

    it('tutorialSkip does NOT mark step as configured', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      w.tutorialSkip(); // skip welcome, move to step 1
      w.tutorialSkip(); // skip appearance
      w.tutorialSkip(); // skip connection
      w.tutorialSkip(); // skip device
      w.tutorialSkip(); // skip quickcmd
      w.tutorialSkip(); // skip transfer
      w.tutorialSkip(); // skip symbols
      w.tutorialSkip(); // skip watch
      w.tutorialSkip(); // skip config
      w.tutorialSkip(); // skip hello_search
      w.tutorialSkip(); // skip hello_inject
      w.tutorialSkip(); // skip hello_verify
      w.tutorialSkip(); // skip hello_unpatch -> complete
      const body = getElement('tutorialBody');
      // All intermediate steps should show skipped
      assertTrue(body.innerHTML.includes('skipped'));
    });
  });

  /* ===========================
     EDGE CASES
     =========================== */

  describe('Tutorial - Edge Cases', () => {
    it('tutorialNext on last step calls finishTutorial', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(13); // last step
      w.tutorialNext(); // should finish
      const overlay = getElement('tutorialOverlay');
      assertFalse(overlay.classList.contains('show'));
      clearTutorialStorage();
    });

    it('tutorialSkip on last step calls finishTutorial', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(13); // last step
      w.tutorialSkip(); // should finish
      const overlay = getElement('tutorialOverlay');
      assertFalse(overlay.classList.contains('show'));
      clearTutorialStorage();
    });

    it('multiple startTutorial calls reset state', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialNext(); // step 1
      w.tutorialNext(); // step 2
      w.startTutorial(); // reset to step 0
      assertEqual(getActiveDotIndex(), 0);
    });
  });

  /* ===========================
     REGRESSION TESTS
     =========================== */

  describe('Tutorial - Regression: config.json deleted re-triggers tutorial', () => {
    it('shouldShowTutorial returns true even with stale localStorage', () => {
      browserGlobals.window.localStorage.setItem(
        'fpbinject_tutorial_completed',
        'true',
      );
      assertTrue(w.shouldShowTutorial({ first_launch: true }));
      clearTutorialStorage();
    });

    it('shouldShowTutorial clears localStorage on first_launch=true', () => {
      browserGlobals.window.localStorage.setItem(
        'fpbinject_tutorial_completed',
        'true',
      );
      w.shouldShowTutorial({ first_launch: true });
      assertEqual(
        browserGlobals.window.localStorage.getItem(
          'fpbinject_tutorial_completed',
        ),
        null,
      );
      clearTutorialStorage();
    });

    it('shouldShowTutorial does not clear localStorage when first_launch=false', () => {
      browserGlobals.window.localStorage.setItem(
        'fpbinject_tutorial_completed',
        'true',
      );
      w.shouldShowTutorial({ first_launch: false });
      assertEqual(
        browserGlobals.window.localStorage.getItem(
          'fpbinject_tutorial_completed',
        ),
        'true',
      );
      clearTutorialStorage();
    });
  });

  describe('Tutorial - Regression: last step shows Finish not Next', () => {
    it('nextBtn text is not "Next" on last step', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(13); // complete (last step)
      const nextBtn = getElement('tutorialNextBtn');
      assertTrue(nextBtn.textContent !== 'Next');
    });

    it('nextBtn text is "Next" on non-last step', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial(); // step 0
      const nextBtn = getElement('tutorialNextBtn');
      assertEqual(nextBtn.textContent, 'Next');
    });
  });

  describe('Tutorial - Regression: appearance step saves config', () => {
    it('appearance language select onchange calls saveConfig', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(1); // appearance step
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('saveConfig'));
    });

    it('appearance theme select onchange calls saveConfig', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(1); // appearance step
      const body = getElement('tutorialBody');
      const themeSelectMatch = body.innerHTML.match(
        /tutorialThemeSelect[\s\S]*?onchange="([^"]*)"/,
      );
      assertTrue(themeSelectMatch !== null);
      assertTrue(themeSelectMatch[1].includes('saveConfig'));
    });
  });

  /* ===========================
     HELLO INJECT STEPS
     =========================== */

  describe('Tutorial - Hello Search Step', () => {
    it('hello_search step renders feature list', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(9); // hello_search
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-list'));
    });

    it('hello_search step mentions fl_hello', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(9); // hello_search
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('fl_hello'));
    });

    it('hello_search step has 3 feature items', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(9); // hello_search
      const body = getElement('tutorialBody');
      const count = (body.innerHTML.match(/tutorial-feature-item/g) || [])
        .length;
      assertEqual(count, 3);
    });
  });

  describe('Tutorial - Hello Inject Step', () => {
    it('hello_inject step renders feature list', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(10); // hello_inject
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-list'));
    });

    it('hello_inject step mentions inject button', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(10); // hello_inject
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('Inject'));
    });

    it('hello_inject step has 3 feature items', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(10); // hello_inject
      const body = getElement('tutorialBody');
      const count = (body.innerHTML.match(/tutorial-feature-item/g) || [])
        .length;
      assertEqual(count, 3);
    });
  });

  describe('Tutorial - Hello Verify Step', () => {
    it('hello_verify step renders feature list', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(11); // hello_verify
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-item'));
    });

    it('hello_verify step mentions fl -c hello command', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(11); // hello_verify
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('fl -c hello'));
    });

    it('hello_verify step has 2 feature items', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(11); // hello_verify
      const body = getElement('tutorialBody');
      const count = (body.innerHTML.match(/tutorial-feature-item/g) || [])
        .length;
      assertEqual(count, 2);
    });

    it('hello_verify step has gate requiring serial tab', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      // tabBtnRaw exists but is NOT active
      const rawBtn = createMockElement('tabBtnRaw');
      mockElements['tabBtnRaw'] = rawBtn;
      w.startTutorial();
      w.tutorialGoTo(11); // hello_verify
      const nextBtn = getElement('tutorialNextBtn');
      assertTrue(nextBtn.disabled);
    });

    it('hello_verify gate passes when serial tab is active', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      const rawBtn = createMockElement('tabBtnRaw');
      rawBtn.classList.add('active');
      mockElements['tabBtnRaw'] = rawBtn;
      w.startTutorial();
      w.tutorialGoTo(11); // hello_verify
      const nextBtn = getElement('tutorialNextBtn');
      assertFalse(nextBtn.disabled);
    });
  });

  describe('Tutorial - Hello Unpatch Step', () => {
    it('hello_unpatch step renders feature list', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(12); // hello_unpatch
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-item'));
    });

    it('hello_unpatch step mentions fl -c hello command', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(12); // hello_unpatch
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('fl -c hello'));
    });

    it('hello_unpatch step has 2 feature items', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(12); // hello_unpatch
      const body = getElement('tutorialBody');
      const count = (body.innerHTML.match(/tutorial-feature-item/g) || [])
        .length;
      assertEqual(count, 2);
    });

    it('hello_unpatch step has gate', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      // Set a slot as occupied so the gate is not yet satisfied
      browserGlobals.window.FPBState.slotStates[0] = {
        occupied: true,
        func: 'fl_hello',
        orig_addr: '0x08001000',
        target_addr: '0x20001000',
        code_size: 64,
      };
      w.startTutorial();
      w.tutorialGoTo(12); // hello_unpatch
      const nextBtn = getElement('tutorialNextBtn');
      assertTrue(nextBtn.disabled);
    });
  });

  /* ===========================
     WATCH STEP
     =========================== */

  describe('Tutorial - Watch Step', () => {
    it('watch step renders feature list', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(7); // watch
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-list'));
    });

    it('watch step has 3 feature items', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(7); // watch
      const body = getElement('tutorialBody');
      const count = (body.innerHTML.match(/tutorial-feature-item/g) || [])
        .length;
      assertEqual(count, 3);
    });

    it('watch step mentions expression', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(7); // watch
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('g_counter'));
    });
  });

  /* ===========================
     SIDEBAR COVERAGE REGRESSION
     =========================== */

  describe('Tutorial - Sidebar Section Coverage', () => {
    it('every sidebar section with details-* has a tutorial step', () => {
      // All sidebar section IDs that exist in the HTML
      const sidebarSections = [
        'details-connection',
        'details-device',
        'details-quick-commands',
        'details-transfer',
        'details-symbols',
        'details-watch',
        'details-configuration',
      ];
      const steps = w.TUTORIAL_STEPS;
      assertTrue(Array.isArray(steps));
      const coveredSidebars = steps
        .filter((s) => s.sidebar)
        .map((s) => s.sidebar);
      for (const section of sidebarSections) {
        assertTrue(
          coveredSidebars.includes(section),
          'Missing tutorial for sidebar: ' + section,
        );
      }
    });

    it('TUTORIAL_STEPS is exported', () => {
      assertTrue(Array.isArray(w.TUTORIAL_STEPS));
      assertTrue(w.TUTORIAL_STEPS.length > 0);
    });
  });

  /* ===========================
     MODAL POSITIONING
     =========================== */

  describe('Tutorial - Modal Positioning', () => {
    it('resetTutorialPosition clears modal styles', () => {
      resetMocks();
      setupTutorialDOM();
      const modal = browserGlobals.document.querySelector('.tutorial-modal');
      modal.style.position = 'fixed';
      modal.style.left = '100px';
      modal.style.top = '200px';
      modal.classList.add('tutorial-modal-positioned');
      w.resetTutorialPosition();
      assertEqual(modal.style.position, '');
      assertEqual(modal.style.left, '');
      assertEqual(modal.style.top, '');
      assertFalse(modal.classList.contains('tutorial-modal-positioned'));
    });

    it('positionModalNearTarget with null resets position', () => {
      resetMocks();
      setupTutorialDOM();
      const modal = browserGlobals.document.querySelector('.tutorial-modal');
      modal.classList.add('tutorial-modal-positioned');
      modal.style.position = 'fixed';
      w.positionModalNearTarget(null);
      assertEqual(modal.style.position, '');
    });

    it('positionModalNearTarget with selector positions modal', () => {
      resetMocks();
      setupTutorialDOM();
      w.positionModalNearTarget('#panelContainer');
      const modal = browserGlobals.document.querySelector('.tutorial-modal');
      assertTrue(modal.classList.contains('tutorial-modal-positioned'));
    });

    it('positionModalNearTarget with already-positioned modal updates position', () => {
      resetMocks();
      setupTutorialDOM();
      const modal = browserGlobals.document.querySelector('.tutorial-modal');
      modal.classList.add('tutorial-modal-positioned');
      modal.style.position = 'fixed';
      w.positionModalNearTarget('#editorContainer');
      assertTrue(modal.style.left !== '');
    });
  });
};

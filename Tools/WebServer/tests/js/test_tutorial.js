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

    it('returns false when localStorage already set', () => {
      browserGlobals.window.localStorage.setItem(
        'fpbinject_tutorial_completed',
        'true',
      );
      const result = w.shouldShowTutorial({ first_launch: true });
      assertFalse(result);
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

    it('shouldShowTutorial returns false after finishTutorial', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.finishTutorial();
      assertFalse(w.shouldShowTutorial({ first_launch: true }));
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
      w.tutorialGoTo(1); // connection
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-list'));
    });

    it('quickcmd step renders feature list', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(3); // quickcmd
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-feature-list'));
    });

    it('complete step renders summary', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(7); // complete
      const body = getElement('tutorialBody');
      assertTrue(body.innerHTML.includes('tutorial-summary'));
    });

    it('complete step shows 🎉 icon', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(7); // complete
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
      w.tutorialGoTo(7); // last step
      const skipBtn = getElement('tutorialSkipBtn');
      assertEqual(skipBtn.style.display, 'none');
    });

    it('skipAll button hidden on last step', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      w.tutorialGoTo(7); // last step
      const skipAllBtn = getElement('tutorialSkipAllBtn');
      assertEqual(skipAllBtn.style.display, 'none');
    });

    it('progress dots rendered for all steps', () => {
      resetMocks();
      clearTutorialStorage();
      setupTutorialDOM();
      w.startTutorial();
      const progress = getElement('tutorialProgress');
      // 9 steps = 9 dot buttons
      const dotCount = (progress.innerHTML.match(/tutorial-dot/g) || []).length;
      assertEqual(dotCount, 9);
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
      w.tutorialGoTo(8);
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
      w.tutorialSkip(); // skip config -> complete
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
      w.tutorialGoTo(7); // last step
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
      w.tutorialGoTo(7); // last step
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
};

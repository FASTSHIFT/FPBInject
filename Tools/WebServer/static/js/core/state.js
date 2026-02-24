/*========================================
  FPBInject Workbench - Global State Module
  ========================================*/

/* ===========================
   GLOBAL STATE
   =========================== */
let isConnected = false;
let toolTerminal = null;
let rawTerminal = null;
let toolFitAddon = null;
let rawFitAddon = null;
let currentTerminalTab = 'tool';
let logPollInterval = null;
let autoInjectPollInterval = null;
let lastAutoInjectStatus = 'idle';
let autoInjectProgressHideTimer = null;
let selectedSlot = 0;
let fpbVersion = 1; // 1=FPB v1 (6 slots), 2=FPB v2 (8 slots)
let slotStates = Array(8)
  .fill()
  .map(() => ({
    occupied: false,
    func: '',
    orig_addr: '',
    target_addr: '',
    code_size: 0,
  }));

// Tabs state
let editorTabs = [];
let activeEditorTab = null;

// Current patch tab info for manual mode
let currentPatchTab = null;

// Ace Editor instances map (tabId -> editor instance)
const aceEditors = new Map();

// File browser state
let fileBrowserCallback = null;
let fileBrowserFilter = '';
let fileBrowserMode = 'file';
let currentBrowserPath = '/';
let selectedBrowserItem = null;

// Log polling state
let toolLogNextId = 0;
let rawLogNextId = 0;
let slotUpdateId = 0;

// Terminal pause state
let terminalPaused = false;
let pausedToolLogs = [];
let pausedRawData = [];

// Export state for other modules
window.FPBState = {
  get isConnected() {
    return isConnected;
  },
  set isConnected(v) {
    isConnected = v;
  },
  get toolTerminal() {
    return toolTerminal;
  },
  set toolTerminal(v) {
    toolTerminal = v;
  },
  get rawTerminal() {
    return rawTerminal;
  },
  set rawTerminal(v) {
    rawTerminal = v;
  },
  get toolFitAddon() {
    return toolFitAddon;
  },
  set toolFitAddon(v) {
    toolFitAddon = v;
  },
  get rawFitAddon() {
    return rawFitAddon;
  },
  set rawFitAddon(v) {
    rawFitAddon = v;
  },
  get currentTerminalTab() {
    return currentTerminalTab;
  },
  set currentTerminalTab(v) {
    currentTerminalTab = v;
  },
  get logPollInterval() {
    return logPollInterval;
  },
  set logPollInterval(v) {
    logPollInterval = v;
  },
  get autoInjectPollInterval() {
    return autoInjectPollInterval;
  },
  set autoInjectPollInterval(v) {
    autoInjectPollInterval = v;
  },
  get lastAutoInjectStatus() {
    return lastAutoInjectStatus;
  },
  set lastAutoInjectStatus(v) {
    lastAutoInjectStatus = v;
  },
  get autoInjectProgressHideTimer() {
    return autoInjectProgressHideTimer;
  },
  set autoInjectProgressHideTimer(v) {
    autoInjectProgressHideTimer = v;
  },
  get selectedSlot() {
    return selectedSlot;
  },
  set selectedSlot(v) {
    selectedSlot = v;
  },
  get fpbVersion() {
    return fpbVersion;
  },
  set fpbVersion(v) {
    fpbVersion = v;
  },
  get slotStates() {
    return slotStates;
  },
  set slotStates(v) {
    slotStates = v;
  },
  get editorTabs() {
    return editorTabs;
  },
  set editorTabs(v) {
    editorTabs = v;
  },
  get activeEditorTab() {
    return activeEditorTab;
  },
  set activeEditorTab(v) {
    activeEditorTab = v;
  },
  get currentPatchTab() {
    return currentPatchTab;
  },
  set currentPatchTab(v) {
    currentPatchTab = v;
  },
  get aceEditors() {
    return aceEditors;
  },
  get fileBrowserCallback() {
    return fileBrowserCallback;
  },
  set fileBrowserCallback(v) {
    fileBrowserCallback = v;
  },
  get fileBrowserFilter() {
    return fileBrowserFilter;
  },
  set fileBrowserFilter(v) {
    fileBrowserFilter = v;
  },
  get fileBrowserMode() {
    return fileBrowserMode;
  },
  set fileBrowserMode(v) {
    fileBrowserMode = v;
  },
  get currentBrowserPath() {
    return currentBrowserPath;
  },
  set currentBrowserPath(v) {
    currentBrowserPath = v;
  },
  get selectedBrowserItem() {
    return selectedBrowserItem;
  },
  set selectedBrowserItem(v) {
    selectedBrowserItem = v;
  },
  get toolLogNextId() {
    return toolLogNextId;
  },
  set toolLogNextId(v) {
    toolLogNextId = v;
  },
  get rawLogNextId() {
    return rawLogNextId;
  },
  set rawLogNextId(v) {
    rawLogNextId = v;
  },
  get slotUpdateId() {
    return slotUpdateId;
  },
  set slotUpdateId(v) {
    slotUpdateId = v;
  },
  get terminalPaused() {
    return terminalPaused;
  },
  set terminalPaused(v) {
    terminalPaused = v;
  },
  get pausedToolLogs() {
    return pausedToolLogs;
  },
  set pausedToolLogs(v) {
    pausedToolLogs = v;
  },
  get pausedRawData() {
    return pausedRawData;
  },
  set pausedRawData(v) {
    pausedRawData = v;
  },
};

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../docs/index.html'), 'utf8');
const marker = "const gd = document.getElementById('temporal_network');";
const markerAt = html.indexOf(marker);
assert.ok(markerAt >= 0, 'focus script is present');
const start = html.lastIndexOf('(function() {', markerAt);
const end = html.indexOf('\n})();', markerAt) + '\n})();'.length;
assert.ok(start >= 0 && end > start, 'focus script is complete');

const controls = new Map();
function control(selector) {
  if (!controls.has(selector)) {
    controls.set(selector, {
      value: '', textContent: '', listeners: {},
      addEventListener(type, handler) { this.listeners[type] = handler; },
      appendChild() {}, setAttribute() {},
    });
  }
  return controls.get(selector);
}
const rail = {querySelector: control};
const domListeners = {};
const documentListeners = {};
const windowListeners = {};
const plotlyListeners = {};
const pendingTimers = [];
const appendedElements = [];
function genericElement() {
  const classes = new Set();
  return {
    id: '', className: '', innerHTML: '', textContent: '',
    style: {}, dataset: {}, children: [],
    classList: {
      toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
      contains(name) { return classes.has(name); },
    },
    appendChild(child) { this.children.push(child); },
    setAttribute() {},
  };
}
const gd = {
  data: [
    {meta: {person_id: 'prachanda'}, opacity: 0.2},
    {meta: {person_id: 'raimajhi'}, opacity: 0.2},
    {meta: {organization_lane_hit_area: true}, opacity: 1},
  ],
  layout: {
    meta: {
      organization_lane_people: {lane_raimajhi: ['raimajhi']},
      organization_lane_options: [{id: 'lane_raimajhi', name: '腊伊玛吉谱系', kind: 'main'}],
      organization_lane_axis_ids: ['lane_background', 'lane_ncp_unified', 'lane_raimajhi'],
      organization_lane_tick_values: [0, 1, 2],
      organization_lane_tick_texts: ['背景', '尼共谱系', '腊伊玛吉谱系'],
      organization_lane_header_height: 170,
    },
    xaxis: {range: [-0.6, 19.6]}, yaxis: {range: [0, 1]},
  },
  _fullLayout: {xaxis: {range: [-0.6, 19.6], _offset: 100, l2p: value => value * 210}},
  getBoundingClientRect: () => ({left: -180, top: -300, bottom: 2100, width: 4110}),
  querySelector(selector) {
    if (selector === '.nsewdrag') return {getBoundingClientRect: () => ({left: 100, top: 200, width: 1000, height: 600})};
    return null;
  },
  addEventListener(type, handler) { (domListeners[type] ||= []).push(handler); },
  on(type, handler) { plotlyListeners[type] = handler; },
};
const document = {
  getElementById: () => gd,
  createElement: tag => tag === 'aside' ? rail : genericElement(),
  head: {appendChild(element) { appendedElements.push(element); }},
  body: {appendChild(element) { appendedElements.push(element); }},
  addEventListener(type, handler) { (documentListeners[type] ||= []).push(handler); },
};
const Plotly = {
  restyle(_gd, update, indices) {
    indices.forEach((index, at) => { gd.data[index].opacity = update.opacity[at]; });
  },
  relayout() {}, Fx: {unhover() {}},
};
const window = {
  setTimeout(handler) { pendingTimers.push(handler); },
  scrollTo() {},
  addEventListener(type, handler) { (windowListeners[type] ||= []).push(handler); },
};
vm.runInNewContext(html.slice(start, end), {document, window, Plotly});

const stickyHeader = appendedElements.find(element => element.id === 'sticky-lane-header');
assert.ok(stickyHeader, 'sticky organization header is created');
assert.equal(stickyHeader.children.length, 3, 'sticky header mirrors all organization columns');
assert.ok(stickyHeader.classList.contains('is-visible'), 'sticky header appears after original labels scroll away');
assert.equal(stickyHeader.style.left, '-180px', 'sticky header follows horizontal page scrolling');
assert.equal(stickyHeader.children[2].style.left, '520px', 'sticky labels use Plotly axis coordinates');
assert.ok(windowListeners.scroll?.length, 'sticky header listens for page scrolling');
assert.ok(plotlyListeners.plotly_relayout, 'sticky header updates after Plotly zooming');

function pointer(type, x, y = 400) {
  const listeners = type === 'pointerdown' ? domListeners[type] : documentListeners[type];
  for (const handler of listeners || []) {
    handler({pointerId: 1, clientX: x, clientY: y});
  }
}
function flushTimers() { while (pendingTimers.length) pendingTimers.shift()(); }
const laneSelect = control('#organization-focus-select');

laneSelect.value = 'lane_raimajhi';
laneSelect.listeners.change();
assert.equal(gd.data[1].opacity, 0.6, 'dropdown highlights organization members');
laneSelect.value = '';
laneSelect.listeners.change();

pointer('pointerdown', 229);
pointer('pointerup', 229); // Plotly dragcover is outside gd; only document receives this.
flushTimers();
assert.equal(laneSelect.value, 'lane_raimajhi', 'blank column click selects its organization');
assert.equal(gd.data[1].opacity, 0.6, 'blank column click highlights its people');

pointer('pointerdown', 229);
pointer('pointerup', 229);
flushTimers();
assert.equal(laneSelect.value, '', 'second blank column click clears organization selection');

gd._fullLayout.xaxis.range = [1, 3];
pointer('pointerdown', 600);
pointer('pointerup', 600);
flushTimers();
assert.equal(laneSelect.value, 'lane_raimajhi', 'column selection follows the current zoom range');
pointer('pointerdown', 600);
pointer('pointerup', 600);
flushTimers();
gd._fullLayout.xaxis.range = [-0.6, 19.6];

pointer('pointerdown', 229);
pointer('pointerup', 229);
plotlyListeners.plotly_click({points: [{curveNumber: 1}]});
flushTimers();
assert.equal(laneSelect.value, '', 'person click takes priority over column selection');
assert.equal(gd.data[1].opacity, 1, 'person click focuses that person');

pointer('pointerdown', 229);
pointer('pointerup', 250);
flushTimers();
assert.equal(laneSelect.value, '', 'drag does not select a column');

console.log('组织列空白区、下拉框和人物点击交互检查通过');

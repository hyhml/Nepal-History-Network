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
const plotlyListeners = {};
const pendingTimers = [];
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
    },
    xaxis: {range: [-0.6, 19.6]}, yaxis: {range: [0, 1]},
  },
  _fullLayout: {xaxis: {range: [-0.6, 19.6]}},
  querySelector(selector) {
    if (selector === '.nsewdrag') return {getBoundingClientRect: () => ({left: 100, top: 200, width: 1000, height: 600})};
    return null;
  },
  addEventListener(type, handler) { (domListeners[type] ||= []).push(handler); },
  on(type, handler) { plotlyListeners[type] = handler; },
};
const document = {
  getElementById: () => gd,
  createElement: tag => tag === 'aside' ? rail : {appendChild() {}},
  head: {appendChild() {}}, body: {appendChild() {}},
  addEventListener() {},
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
};
vm.runInNewContext(html.slice(start, end), {document, window, Plotly});

function pointer(type, x, y = 400) {
  for (const handler of domListeners[type] || []) {
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
pointer('pointerup', 229);
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

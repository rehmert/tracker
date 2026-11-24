'use strict';
/* Release 779 — browser-like Node DOM regression for shared time input. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

function target(x = {}) {
  const callbacks = {};
  x.addEventListener = (name, fn) => (callbacks[name] ||= []).push(fn);
  x.dispatchEvent = e => {
    for (const fn of callbacks[e.type] || []) fn(e);
  };
  return x;
}
function element(tag) {
  const x = target({
    tagName: tag.toUpperCase(), value: '', type: 'text', dataset: {},
    children: [], required: false, disabled: false, readOnly: false,
    hidden: false, tabIndex: 0, invalid: '', className: '', attrs: {},
  });
  const classes = new Set();
  x.classList = {add: name => classes.add(name),
                 contains: name => classes.has(name)};
  x.setAttribute = (key, value) => {x.attrs[key] = value;};
  x.setCustomValidity = message => {x.invalid = message;};
  x.append = (...children) => {
    children.forEach(child => {child.parentNode = x; x.children.push(child);});
  };
  x.insertBefore = (child, reference) => {
    const i = x.children.indexOf(reference);
    assert(i >= 0, 'insertion target present');
    x.children.splice(i, 0, child);
    child.parentNode = x;
  };
  return x;
}
function clockSource(kind, value, required) {
  const parent = element('label');
  const original = element('input');
  const form = target({matches: () => false});
  original.type = kind;
  original.name = kind === 'time' ? 'at_time' : 'logged_at';
  original.value = value;
  original.required = required;
  original.form = form;
  original.parentNode = parent;
  parent.children.push(original);
  return {original, parent, form};
}
const time = clockSource('time', '07:15', false);
const timestamp = clockSource('datetime-local', '2026-11-24T20:30', true);
const sources = [time.original, timestamp.original];
let onMutation = null;
const document = target({
  readyState: 'complete',
  body: element('body'),
  createElement: element,
  querySelectorAll: () => sources,
});
const window = target({});
class Event { constructor(type, options) {this.type = type; this.bubbles = options?.bubbles;} }
class MutationObserver {
  constructor(fn) {onMutation = fn;}
  observe(root, options) {assert(root === document.body && options.subtree);}
}
vm.runInNewContext(
  fs.readFileSync('app/static/js/tracker-time24-global713.js', 'utf8'),
  {document, window, MutationObserver, Event, Date, queueMicrotask}
);
assert.equal(window.trackerTime24Global713, true);
assert(time.original.hidden && timestamp.original.hidden);
assert(time.original.dataset.tracker24hEnhanced === 'true');
const timeClock = time.parent.children[0];
const stampContainer = timestamp.parent.children[0];
const stampDate = stampContainer.children[0];
const stampClock = stampContainer.children[1];
assert.equal(timeClock.value, '07:15');
assert.equal(stampDate.value, '2026-11-24');
assert.equal(stampClock.value, '20:30');
assert.equal(timeClock.name, undefined);
assert.equal(stampClock.name, undefined);

function enter(input, original, typed, expected) {
  input.value = typed;
  input.dispatchEvent({type:'input'});
  assert.equal(original.value, expected, 'named native field for '+typed);
  assert.equal(input.invalid, '', 'custom validity for '+typed);
  input.dispatchEvent({type:'blur'});
  const display = expected.split('T').pop();
  assert.equal(input.value, display, 'normalized display for '+typed);
}
enter(timeClock, time.original, '0730', '07:30');
enter(timeClock, time.original, '930', '09:30');
enter(timeClock, time.original, '2130', '21:30');
enter(timeClock, time.original, '0000', '00:00');
enter(timeClock, time.original, '2359', '23:59');
enter(timeClock, time.original, '14:05', '14:05');
enter(stampClock, timestamp.original, '930', '2026-11-24T09:30');
enter(stampClock, timestamp.original, '2130', '2026-11-24T21:30');
stampDate.value = '2026-12-03';
stampDate.dispatchEvent({type:'input'});
assert.equal(timestamp.original.value, '2026-12-03T21:30');

for (const invalid of ['2400', '2360', '999', '25:00', '12:99', 'oops']) {
  timeClock.value = invalid;
  timeClock.dispatchEvent({type:'input'});
  assert.equal(time.original.value, '', 'invalid HHMM must not post: '+invalid);
  assert(timeClock.invalid, 'invalid time should show validation error: '+invalid);
}
timeClock.value = '';
timeClock.dispatchEvent({type:'input'});
assert.equal(timeClock.invalid, '', 'optional empty time allowed');
assert.equal(time.original.value, '');
timeClock.value = '0930';
time.form.dispatchEvent({type:'submit'});
assert.equal(time.original.value, '09:30');
assert.equal(timeClock.value, '09:30');

time.original.value = '12:25';
time.original.dispatchEvent({type:'change'});
assert.equal(timeClock.value, '12:25', 'programmatic sync preserved');

(async () => {
  const newlyAdded = clockSource('time', '06:45', false);
  sources.push(newlyAdded.original);
  onMutation([{addedNodes: [newlyAdded.parent]}]);
  await new Promise(resolve => setImmediate(resolve));
  assert(newlyAdded.original.hidden, 'dynamically added control enhanced');
  const proxy = newlyAdded.parent.children[0];
  enter(proxy, newlyAdded.original, '2240', '22:40');
  document.dispatchEvent({type:'htmx:afterSwap'});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(newlyAdded.parent.children.length, 2,
               'no duplicate time proxy after HTMX enhancement');
  console.log('RELEASE_779_GLOBAL_TIME_INPUT=PASSED');
})().catch(error => {console.error(error); process.exitCode = 1;});

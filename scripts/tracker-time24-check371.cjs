const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

function eventTarget(obj = {}) {
  obj._callbacks = {};

  obj.addEventListener = function(name, fn) {
    (this._callbacks[name] ||= []).push(fn);
  };

  obj.dispatchEvent = function(event) {
    for (const fn of this._callbacks[event.type] || []) {
      fn(event);
    }
  };

  return obj;
}

function element(tag) {
  return eventTarget({
    tagName: tag.toUpperCase(),
    dataset: {},
    value: '',
    required: false,
    hidden: false,
    children: [],
    style: {},

    setCustomValidity(message) {
      this.invalid = message;
    },

    setAttribute(key, value) {
      this[key] = value;
    },

    append(...children) {
      this.children.push(...children);
    },

    insertBefore(child) {
      this.children.push(child);
    }
  });
}

const original = element('input');
original.value = '2026-11-04T21:07';
original.type = 'datetime-local';

const label = element('label');
original.closest = () => label;

const form = eventTarget({
  dataset: {},
  querySelector: () => original
});

const document = eventTarget({
  readyState: 'complete',
  body: eventTarget(),
  createElement: element,
  querySelectorAll: () => [form]
});

const context = {
  document,
  Date,
  Event: class {
    constructor(type, options) {
      this.type = type;
      this.bubbles = options?.bubbles;
    }
  },
  queueMicrotask
};

vm.runInNewContext(
  fs.readFileSync(
    'app/static/js/tracker-time24-371.js',
    'utf8'
  ),
  context
);

assert(original.hidden);

const layout = label.children[0];
const date = layout.children[0];
const time = layout.children[1];

assert.equal(date.value, '2026-11-04');
assert.equal(time.value, '21:07');

time.value = '09:15';
time.dispatchEvent({type:'input'});
assert.equal(original.value, '2026-11-04T09:15');

time.value = '29:15';
time.dispatchEvent({type:'input'});
assert.equal(original.value, '');
assert(time.invalid);

original.value = '2026-11-04T23:55';
original.dispatchEvent({type:'change'});
assert.equal(time.value, '23:55');

console.log(
  'PASS: 24-hour form synchronization and validation'
);

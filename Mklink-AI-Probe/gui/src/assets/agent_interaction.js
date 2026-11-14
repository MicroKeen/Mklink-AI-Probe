/* agent-ui-dev agent-frontend/1 runtime; adapted to retain MKLink action results. */
(function(root) {
  'use strict';
  const protocol = 'agent-frontend/1';
  const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const clone = value => JSON.parse(JSON.stringify(value));
  const fail = (code, message) => { throw Object.assign(new Error(message), { code }); };
  const ensure = (condition, code, message) => { if (!condition) fail(code, message); };
  const id = value => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,80}$/.test(value);
  function keys(value, allowed, required = allowed) {
    ensure(plain(value) && Object.keys(value).every(key => allowed.includes(key)) && required.every(key => Object.hasOwn(value, key)), 'INVALID_INPUT', 'Unexpected or missing fields');
  }
  function validateCommand(command) {
    keys(command, ['protocol','session_id','page_id','command_id','expect_revision','deadline','action','args']);
    ensure(command.protocol === protocol, 'PROTOCOL_MISMATCH', 'Unsupported interaction protocol');
    ensure(['session_id','page_id','command_id','action'].every(key => id(command[key])), 'INVALID_INPUT', 'Invalid identifier');
    ensure(Number.isSafeInteger(command.expect_revision) && command.expect_revision >= 0 && Number.isSafeInteger(command.deadline), 'INVALID_INPUT', 'Invalid revision or deadline');
    ensure(plain(command.args), 'INVALID_INPUT', 'args must be an object');
  }
  const canonical = value => Array.isArray(value) ? value.map(canonical) : plain(value) ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
  const signature = command => JSON.stringify(canonical(command));
  function validateArgs(args, schema) {
    function checkSchema(rule, depth = 0) {
      ensure(depth <= 8 && plain(rule), 'SCHEMA_UNSUPPORTED', 'Invalid or deeply nested schema');
      const common = ['type','description'];
      if (rule.type === 'object') {
        ensure(rule.additionalProperties === false && plain(rule.properties) && Array.isArray(rule.required), 'SCHEMA_UNSUPPORTED', 'Expected a strict object schema');
        ensure(Object.keys(rule).every(key => [...common,'properties','required','additionalProperties'].includes(key)) && rule.required.every(key => typeof key === 'string' && Object.hasOwn(rule.properties,key)), 'SCHEMA_UNSUPPORTED', 'Invalid object schema');
        for (const item of Object.values(rule.properties)) checkSchema(item, depth + 1);
      } else if (rule.type === 'array') {
        ensure(Object.keys(rule).every(key => [...common,'items','minItems','maxItems'].includes(key)) && Number.isSafeInteger(rule.maxItems) && rule.maxItems >= 0 && rule.maxItems <= 500 && (rule.minItems === undefined || Number.isSafeInteger(rule.minItems) && rule.minItems >= 0 && rule.minItems <= rule.maxItems), 'SCHEMA_UNSUPPORTED', 'Arrays require a bounded length');
        checkSchema(rule.items, depth + 1);
      } else {
        ensure(['string','number','integer','boolean'].includes(rule.type) && Object.keys(rule).every(key => [...common,'enum','minimum','maximum','maxLength'].includes(key)), 'SCHEMA_UNSUPPORTED', 'Unsupported field schema');
        ensure(rule.enum === undefined || Array.isArray(rule.enum) && rule.enum.length > 0, 'SCHEMA_UNSUPPORTED', 'Invalid enum');
        for (const bound of ['minimum','maximum']) ensure(rule[bound] === undefined || ['number','integer'].includes(rule.type) && Number.isFinite(rule[bound]), 'SCHEMA_UNSUPPORTED', 'Invalid numeric bound');
        ensure(rule.maxLength === undefined || rule.type === 'string' && Number.isSafeInteger(rule.maxLength) && rule.maxLength >= 0, 'SCHEMA_UNSUPPORTED', 'Invalid string bound');
      }
    }
    function checkValue(value, rule) {
      if (rule.type === 'object') {
        keys(value, Object.keys(rule.properties), rule.required);
        for (const key of Object.keys(value)) checkValue(value[key], rule.properties[key]);
      } else if (rule.type === 'array') {
        ensure(Array.isArray(value) && value.length >= (rule.minItems || 0) && value.length <= rule.maxItems, 'INVALID_INPUT', 'Invalid array length');
        for (const item of value) checkValue(item, rule.items);
      } else {
        const valid = rule.type === 'integer' ? Number.isSafeInteger(value) : rule.type === 'number' ? typeof value === 'number' && Number.isFinite(value) : typeof value === rule.type;
        ensure(valid && (!rule.enum || rule.enum.includes(value)) && (rule.minimum === undefined || value >= rule.minimum) && (rule.maximum === undefined || value <= rule.maximum) && (rule.maxLength === undefined || value.length <= rule.maxLength), 'INVALID_INPUT', 'Invalid field value');
      }
    }
    checkSchema(schema); checkValue(args, schema);
  }
  function create({ session_id, page_id, adapter }) {
    ensure(id(session_id) && id(page_id), 'INVALID_INPUT', 'Invalid page identity');
    let revision = 0, fingerprint, disposed = false, active = null;
    const records = new Map();
    function read() {
      const value = clone(adapter.read());
      const next = JSON.stringify(value);
      if (fingerprint !== undefined && fingerprint !== next) revision++;
      fingerprint = next;
      return { revision, value };
    }
    const report = () => ({ protocol, session_id, page_id, title: adapter.title, catalog: clone(adapter.catalog()), actions: clone(adapter.actions), state: read() });
    const receipts = () => [...records.values()].map(record => clone(record.receipt));
    function execute(input) {
      validateCommand(input);
      const command = clone(input), content = signature(command);
      ensure(command.session_id === session_id && command.page_id === page_id, 'WRONG_TARGET', 'Command belongs to another page');
      const old = records.get(command.command_id);
      if (old) {
        ensure(old.signature === content, 'ID_CONFLICT', 'Command ID already has different content');
        return { ...clone(old.receipt), duplicate: true };
      }
      ensure(records.size < 500, 'SESSION_LIMIT', 'Command history is full; open a new page session');
      const record = { signature: content, receipt: { command_id: command.command_id, action: command.action } };
      records.set(command.command_id, record);
      function finish(status, code, result, message) {
        revision++;
        let state;
        try { state = read(); } catch { status = 'unknown'; code = 'STATE_UNAVAILABLE'; }
        record.receipt = { command_id:command.command_id, action:command.action, status, ...(code ? { code } : {}), ...(message ? { message: String(message).slice(0, 2000) } : {}), ...(result !== undefined ? { result: clone(result) } : {}), ...(state ? { state } : {}) };
        return clone(record.receipt);
      }
      try {
        ensure(!disposed, 'DISPOSED', 'Page is disposed');
        ensure(Date.now() <= command.deadline, 'EXPIRED', 'Command deadline elapsed');
        ensure(command.deadline <= Date.now() + 30000, 'EXPIRED', 'Deadline exceeds the next 30 seconds');
        ensure(active === null, 'BUSY', 'Another action is running');
        ensure(![...records.values()].some(item => item.receipt.status === 'unknown'), 'BUSY', 'An earlier action has an unknown outcome');
        ensure(read().revision === command.expect_revision, 'STALE_REVISION', 'Read the current page state before acting');
        ensure(Object.hasOwn(adapter.actions, command.action), 'UNKNOWN_ACTION', 'Action is not advertised');
        validateArgs(command.args, adapter.actions[command.action].inputSchema);
        if (adapter.validate) adapter.validate(command.action, command.args);
      } catch (error) { return finish('rejected', error.code || 'INVALID_INPUT', undefined, error.message); }
      try {
        const result = adapter.execute(command.action, command.args, command);
        if (result && typeof result.then === 'function') {
          active = command.command_id;
          finish('accepted');
          Promise.resolve(result).then(value => {
            if (!disposed) finish('completed', undefined, value);
          }, error => { if (!disposed) finish(error?.unknown ? 'unknown' : 'failed', id(error?.code) ? error.code : 'ACTION_FAILED', undefined, error?.message); }).finally(() => { active = null; });
          return clone(record.receipt);
        }
        return finish('applied', undefined, result);
      } catch (error) { return finish(error?.unknown ? 'unknown' : 'failed', 'ACTION_FAILED', undefined, error?.message); }
    }
    function dispose() {
      disposed = true;
      if (active) records.get(active).receipt = { ...records.get(active).receipt, status: 'unknown', code: 'DISPOSED' };
      adapter.dispose?.();
    }
    return { report, read, execute, receipts, dispose, invalidate: () => { revision++; } };
  }
  const api = { protocol, create, validateCommand, validateArgs, keys, ensure, id, signature };
  root.AgentInteraction = api;
})(globalThis);

import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

const source = readFileSync(new URL('../site-data.js', import.meta.url), 'utf8');
function environment(storage = {}) {
  const localStorage = new Proxy(storage, { get(target, key) {
    if (key === 'getItem') return k => target[k] || null;
    if (key === 'setItem') return (k, value) => { target[k] = value; };
    if (key === 'removeItem') return k => { delete target[k]; };
    return target[key];
  }});
  const window = { dispatchEvent() {}, getUid: () => 'uid-alice' };
  runInNewContext(source, { window, localStorage, AbortController, setTimeout, clearTimeout, performance,
    CustomEvent: class {}, fetch: () => { throw Error('unexpected request'); } });
  return window.CodeBugData;
}

test('snapshots survive navigation and SWR displays them before the network completes', async () => {
  const storage = {};
  environment(storage).write('catalog', ['saved']);
  const data = environment(storage);
  let resolve;
  const network = new Promise(r => { resolve = r; });
  const renders = [];
  const result = data.swr('catalog', () => network, (value, cached) => renders.push({value,cached}), {force:true});
  assert.equal(renders[0].value[0], 'saved');
  assert.equal(renders[0].cached, true);
  resolve(['fresh']);
  await result;
  assert.equal(renders[1].value[0], 'fresh');
});

test('concurrent profile readers share one request', async () => {
  const data = environment();
  let requests = 0;
  const loader = async () => { requests++; return {login:'alice'}; };
  const [a,b] = await Promise.all([data.load('profile:alice',loader),data.load('profile:alice',loader)]);
  assert.equal(requests, 1);
  assert.equal(a, b);
});

test('sign-out cannot be undone by a late response', async () => {
  const storage = {};
  const data = environment(storage);
  let resolve;
  const result = data.load('private:uid-alice:training', () => new Promise(r => { resolve = r; }));
  await Promise.resolve();
  data.invalidate('private:');
  resolve({solved:10});
  await result;
  assert.equal(data.read('private:uid-alice:training'), null);
  assert.equal(environment(storage).read('private:uid-alice:training'), null);
});

test('network failure keeps the last good snapshot', async () => {
  const data = environment();
  data.write('catalog', ['saved']);
  await assert.rejects(data.load('catalog', () => Promise.reject(Error('offline')), {force:true}));
  assert.equal(data.read('catalog')[0], 'saved');
});

test('an explicit refresh supersedes an older in-flight response', async () => {
  const data = environment();
  let finishOld;
  const old = data.load('submissions:alice', () => new Promise(r => { finishOld = r; }));
  await Promise.resolve();
  await data.load('submissions:alice', async () => ['new verdict'], {force:true});
  finishOld(['queued']);
  await old;
  assert.equal(data.read('submissions:alice')[0], 'new verdict');
});

import { strict as assert } from 'assert';
import { test } from 'node:test';
import { isAuthorized, isLoopback } from '../auth';

const basic = (user: string, password: string) => 'Basic ' + Buffer.from(`${user}:${password}`).toString('base64');

test('the right password passes with any user name', () => {
    assert.equal(isAuthorized(basic('anyone', 'secret'), 'secret'), true);
    assert.equal(isAuthorized(basic('', 'with:colon'), 'with:colon'), true);
});

test('anything else is refused', () => {
    assert.equal(isAuthorized(basic('anyone', 'wrong'), 'secret'), false);
    assert.equal(isAuthorized(undefined, 'secret'), false);
    assert.equal(isAuthorized('Bearer abc', 'secret'), false);
    assert.equal(isAuthorized('Basic !!!', 'secret'), false);
});

test('an empty configured password never matches', () => {
    assert.equal(isAuthorized(basic('anyone', ''), ''), false);
});

test('only this machine counts as loopback', () => {
    assert.equal(isLoopback('127.0.0.1'), true);
    assert.equal(isLoopback('::1'), true);
    assert.equal(isLoopback('::ffff:127.0.0.1'), true);
    assert.equal(isLoopback('192.168.0.20'), false);
    assert.equal(isLoopback(undefined), false);
});

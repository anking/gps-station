import { strict as assert } from 'assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { test } from 'node:test';
import { driverModeArgs, isSafeCommandParams, isValidFixedPosition, loadBaseMode, parseModeCommand, saveBaseMode } from '../baseMode';

test('fixed positions keep the numbers exactly as typed', () => {
    assert.deepEqual(parseModeCommand('RESTART_FIXED:40.1234560:-80.1234567:300.25'), { kind: 'fixed', position: '40.1234560:-80.1234567:300.25' });
});

test('survey settings are read as numbers', () => {
    assert.deepEqual(parseModeCommand('RESTART_SURVEY:2.5:120'), { kind: 'survey', accuracy: 2.5, time: 120 });
});

test('invalid commands are not remembered', () => {
    for (const command of ['RESTART_FIXED:95:10:300', 'RESTART_FIXED:10:190:300', 'RESTART_FIXED:0:0:100', 'RESTART_FIXED:1:2', 'RESTART_FIXED:a:b:c',
        'RESTART_SURVEY:0:60', 'RESTART_SURVEY:3:0', 'RESTART_SURVEY:3:70000', 'HELLO']) {
        assert.equal(parseModeCommand(command), null, command);
    }
});

test('a fixed position is validated', () => {
    assert.equal(isValidFixedPosition('40.1:-80.1:300'), true);
    assert.equal(isValidFixedPosition('40.1:-80.1:20000'), false);
    assert.equal(isValidFixedPosition(''), false);
});

test('a negative latitude reaches the driver as one argument', () => {
    assert.deepEqual(driverModeArgs({ kind: 'fixed', position: '-33.8:151.2:58' }), ['--fixed-position=-33.8:151.2:58']);
});

test('survey settings reach the driver', () => {
    assert.deepEqual(driverModeArgs({ kind: 'survey', accuracy: 3, time: 60 }), ['--rtcm-accuracy-req', '3', '--rtcm-survey-time', '60']);
});

test('browser parameters cannot smuggle a second command', () => {
    assert.equal(isSafeCommandParams('40.1:-80.1:300'), true);
    assert.equal(isSafeCommandParams('1:2\nRESTART_SURVEY:1:1'), false);
    assert.equal(isSafeCommandParams({ a: 1 }), false);
    assert.equal(isSafeCommandParams('9'.repeat(101)), false);
});

test('the mode survives a restart, and a bad file falls back', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'base-mode-'));
    const file = path.join(dir, 'data', 'base-mode.json');
    const fallback = { kind: 'survey', accuracy: 3, time: 60 } as const;

    assert.deepEqual(loadBaseMode(file, fallback), fallback);

    saveBaseMode(file, { kind: 'fixed', position: '40.1:-80.1:300' });
    assert.deepEqual(loadBaseMode(file, fallback), { kind: 'fixed', position: '40.1:-80.1:300' });

    fs.writeFileSync(file, '{ not json');
    assert.deepEqual(loadBaseMode(file, fallback), fallback);

    fs.writeFileSync(file, JSON.stringify({ kind: 'fixed', position: '95:10:300' }));
    assert.deepEqual(loadBaseMode(file, fallback), fallback);
});

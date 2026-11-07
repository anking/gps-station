import * as fs from 'fs';
import * as path from 'path';

/**
 * What the base should do at start-up. It outlives a reboot, because a base that quietly goes back to
 * surveying moves every rover position by however much the new survey differs.
 */
export type BaseMode =
    | { kind: 'survey'; accuracy: number; time: number }
    | { kind: 'fixed'; position: string };

const NUMBER = /^-?\d+(\.\d+)?$/;

export const isValidFixedPosition = (position: string): boolean => {
    const parts = position.split(':');
    if (parts.length !== 3 || !parts.every(part => NUMBER.test(part))) return false;

    const [latitude, longitude, height] = parts.map(Number);
    return Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180 && height >= -500 && height <= 9000 && (latitude !== 0 || longitude !== 0);
};

/**
 * Reads a RESTART_SURVEY or RESTART_FIXED command. Returns null when it is not a valid mode to remember.
 */
export const parseModeCommand = (command: string): BaseMode | null => {
    const [name, ...values] = command.trim().split(':');

    if (name === 'RESTART_SURVEY' && values.length === 2 && values.every(value => NUMBER.test(value))) {
        const [accuracy, time] = values.map(Number);
        return accuracy > 0 && time > 0 && time <= 65535 ? { kind: 'survey', accuracy, time } : null;
    }

    if (name === 'RESTART_FIXED' && isValidFixedPosition(values.join(':'))) {
        return { kind: 'fixed', position: values.join(':') };
    }

    return null;
};

/**
 * Only these characters reach the driver: a line break would let a browser send a second command.
 */
export const isSafeCommandParams = (params: unknown): params is string =>
    typeof params === 'string' && params.length <= 100 && /^[0-9.:-]*$/.test(params);

export const driverModeArgs = (mode: BaseMode): string[] =>
    mode.kind === 'fixed'
        ? [`--fixed-position=${mode.position}`]
        : ['--rtcm-accuracy-req', mode.accuracy.toString(), '--rtcm-survey-time', mode.time.toString()];

export const loadBaseMode = (file: string, fallback: BaseMode): BaseMode => {
    try {
        const saved = JSON.parse(fs.readFileSync(file, 'utf8'));
        if (saved.kind === 'fixed' && isValidFixedPosition(saved.position)) return saved;
        if (saved.kind === 'survey' && saved.accuracy > 0 && saved.time > 0) return saved;
    } catch {
        // No saved mode yet, or an unreadable file: start from the configuration
    }

    return fallback;
};

export const saveBaseMode = (file: string, mode: BaseMode): void => {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(mode));
};

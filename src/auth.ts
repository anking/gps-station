import { createHash, timingSafeEqual } from 'crypto';
import type { NextFunction, Request, Response } from 'express';
import type { Socket } from 'socket.io';

const LOOPBACK = new Set(['127.0.0.1', '::1', '::ffff:127.0.0.1']);

export const isLoopback = (address?: string): boolean => address !== undefined && LOOPBACK.has(address);

const sha256 = (text: string): Buffer => createHash('sha256').update(text).digest();

/**
 * Checks an HTTP Basic header. Any user name is accepted: there is one password for this device.
 */
export const isAuthorized = (header: string | undefined, password: string): boolean => {
    if (!password || !header?.startsWith('Basic ')) return false;

    const decoded = Buffer.from(header.slice('Basic '.length), 'base64').toString('utf8');
    const separator = decoded.indexOf(':');
    if (separator < 0) return false;

    return timingSafeEqual(sha256(decoded.slice(separator + 1)), sha256(password));
};

/**
 * The kiosk screen runs on this machine and has no way to type a password, so loopback is always allowed.
 */
export const httpAuth = (password: string) => (req: Request, res: Response, next: NextFunction): void => {
    if (isLoopback(req.socket.remoteAddress) || isAuthorized(req.headers.authorization, password)) {
        next();
        return;
    }

    res.set('WWW-Authenticate', 'Basic realm="GPS Station", charset="UTF-8"').status(401).send('Password required');
};

/**
 * Socket.IO starts on HTTP polling, which carries the browser's Basic credentials, so this also covers the WebSocket
 * upgrade of the same session. It guards commands such as POWER_OFF.
 */
export const socketAuth = (password: string) => (socket: Socket, next: (err?: Error) => void): void => {
    if (isLoopback(socket.handshake.address) || isAuthorized(socket.handshake.headers.authorization, password)) {
        next();
        return;
    }

    next(new Error('Password required'));
};

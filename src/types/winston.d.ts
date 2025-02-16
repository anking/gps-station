import * as winston from 'winston';
import { TransformableInfo } from 'winston';

declare module 'winston' {
    interface LogLevels {
        f9p: number;
        chromium: number;
    }

    interface Logger {
        f9p(message: string): void;
        chromium(message: string): void;
    }
}

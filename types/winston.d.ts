import * as winston from 'winston';
import { TransformableInfo } from 'winston';

declare module 'winston' {
    interface LogLevels {
        f9p: number; // Define the custom level here
    }

    interface Logger {
        f9p(message: string): void;
    }
}

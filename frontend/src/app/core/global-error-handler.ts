import { ErrorHandler, Injectable } from '@angular/core';

import { LoggerService } from './logger.service';

@Injectable()
export class GlobalErrorHandler implements ErrorHandler {
  constructor(private readonly logger: LoggerService) {}

  handleError(error: unknown): void {
    this.logger.error('Unhandled error', { error: toErrorInfo(error) });
  }
}

const toErrorInfo = (error: unknown): Record<string, unknown> => {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack,
    };
  }
  if (typeof error === 'string') {
    return { message: error };
  }
  if (error && typeof error === 'object') {
    try {
      return { value: JSON.parse(JSON.stringify(error)) as unknown };
    } catch {
      return { value: String(error) };
    }
  }
  return { value: error };
};


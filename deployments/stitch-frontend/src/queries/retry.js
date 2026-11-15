export const MAX_RETRIES = 3;

export function isRetriableError(error) {
  const status = error?.status;

  if (typeof status === "number") {
    return status === 408 || status === 429 || status >= 500;
  }

  return error instanceof TypeError;
}

export function shouldRetryQuery(failureCount, error) {
  return failureCount <= MAX_RETRIES && isRetriableError(error);
}

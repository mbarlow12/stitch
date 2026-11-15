import { useEffect, useState } from "react";

export const DEFAULT_DEBOUNCE_MS = 300;

export function useDebouncedValue(value, delayMs = DEFAULT_DEBOUNCE_MS) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timeoutId = setTimeout(() => setDebouncedValue(value), delayMs);
    return () => clearTimeout(timeoutId);
  }, [value, delayMs]);

  return debouncedValue;
}

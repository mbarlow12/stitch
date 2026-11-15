const HEALTH_PATH = "/health/details";

function healthUrl(baseUrl) {
  return `${baseUrl.replace(/\/+$/, "")}${HEALTH_PATH}`;
}

export function prewarmApi(config) {
  const baseUrl = config?.apiBaseUrl;

  if (typeof baseUrl !== "string" || !baseUrl) {
    return Promise.resolve();
  }

  return fetch(healthUrl(baseUrl), { cache: "no-store" }).then(
    () => undefined,
    () => undefined,
  );
}

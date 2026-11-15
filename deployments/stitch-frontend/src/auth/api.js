export function createAuthenticatedFetcher(config, getAccessTokenSilently) {
  return async (url, options = {}) => {
    const token = await getAccessTokenSilently({
      authorizationParams: { audience: config.auth0.audience },
    });
    const headers = new Headers(options.headers);
    headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { ...options, headers });
  };
}

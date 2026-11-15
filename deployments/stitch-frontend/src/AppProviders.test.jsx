import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { useQueryClient } from "@tanstack/react-query";
import { Auth0Provider } from "@auth0/auth0-react";
import { AppProviders } from "./AppProviders";

vi.mock("@auth0/auth0-react", () => ({
  Auth0Provider: vi.fn(({ children }) => children),
  useAuth0: vi.fn().mockReturnValue({
    isAuthenticated: true,
    isLoading: false,
    error: null,
    user: { sub: "test-user-id", email: "test@example.com" },
    getAccessTokenSilently: vi.fn().mockResolvedValue("test-access-token"),
    loginWithRedirect: vi.fn(),
    logout: vi.fn(),
  }),
}));

const TEST_CONFIG = {
  auth0: {
    domain: "example.auth0.com",
    clientId: "client-id",
    audience: "https://stitch-api.local",
  },
};

describe("AppProviders", () => {
  it("persists the Auth0 session across reloads (STIT-581)", () => {
    render(
      <AppProviders config={TEST_CONFIG}>
        <div>App Content</div>
      </AppProviders>,
    );

    expect(Auth0Provider).toHaveBeenCalledTimes(1);
    expect(Auth0Provider.mock.calls[0][0]).toMatchObject({
      cacheLocation: "localstorage",
      useRefreshTokens: true,
    });
  });

  it("hands the cold-start retry policy down to every query", () => {
    let defaults;
    function Probe() {
      defaults = useQueryClient().getDefaultOptions();
      return null;
    }

    render(
      <AppProviders config={TEST_CONFIG}>
        <Probe />
      </AppProviders>,
    );

    const retry = defaults.queries?.retry;

    expect(typeof retry).toBe("function");

    const httpError = (status) => Object.assign(new Error(status), { status });

    expect(retry(1, httpError(503))).toBe(true);
    expect(retry(1, new TypeError("Failed to fetch"))).toBe(true);
    expect(retry(1, httpError(404))).toBe(false);
    expect(retry(99, httpError(503))).toBe(false);

    expect(defaults.mutations?.retry).toBeUndefined();
  });

  it("renders children through AuthGate when authenticated", () => {
    render(
      <AppProviders config={TEST_CONFIG}>
        <div>App Content</div>
      </AppProviders>,
    );

    expect(screen.getByText("App Content")).toBeInTheDocument();
  });
});

import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useQueryClient } from "@tanstack/react-query";
import LoginPage from "../components/LoginPage";

const SESSION_EXPIRED_ERRORS = new Set([
  "login_required",
  "missing_refresh_token",
  "invalid_grant",
]);

const REDIRECT_GUARD_KEY = "stitch.auth.sessionRedirectAt";
const REDIRECT_GUARD_MS = 5 * 60_000;

function isSessionExpired(error) {
  return SESSION_EXPIRED_ERRORS.has(error?.error) || error?.status === 401;
}

function claimRedirect() {
  try {
    const last = Number(window.sessionStorage.getItem(REDIRECT_GUARD_KEY));
    if (last && Date.now() - last < REDIRECT_GUARD_MS) return false;
    window.sessionStorage.setItem(REDIRECT_GUARD_KEY, String(Date.now()));
    return true;
  } catch {
    return false;
  }
}

export default function AuthGate({ children }) {
  const { isLoading, isAuthenticated, error, loginWithRedirect } = useAuth0();
  const queryClient = useQueryClient();

  useEffect(() => {
    let redirecting = false;
    function handleCacheEvent(event) {
      if (
        redirecting ||
        event.type !== "updated" ||
        event.action.type !== "error" ||
        !isSessionExpired(event.action.error)
      ) {
        return;
      }
      redirecting = true;
      if (!claimRedirect()) return;
      loginWithRedirect({
        appState: {
          returnTo: window.location.pathname + window.location.search,
        },
      });
    }
    const unsubscribeQueries = queryClient
      .getQueryCache()
      .subscribe(handleCacheEvent);
    const unsubscribeMutations = queryClient
      .getMutationCache()
      .subscribe(handleCacheEvent);
    return () => {
      unsubscribeQueries();
      unsubscribeMutations();
    };
  }, [queryClient, loginWithRedirect]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <p className="text-lg text-ink-muted">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <p className="text-lg text-danger">
          Authentication error: {error.message}
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return children;
}

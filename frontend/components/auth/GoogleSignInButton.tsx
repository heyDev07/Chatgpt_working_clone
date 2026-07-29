import { API_BASE_URL } from "@/lib/api/client";

export function GoogleSignInButton() {
  return (
    <>
      <div className="flex items-center gap-3 w-full max-w-sm">
        <div className="h-px flex-1 bg-black/10 dark:bg-white/15" />
        <span className="text-xs text-black/40 dark:text-white/40">or</span>
        <div className="h-px flex-1 bg-black/10 dark:bg-white/15" />
      </div>
      {/* Plain link, not a fetch-then-navigate handler - /auth/google/authorize needs no Bearer
          token (nobody's logged in yet), so there's nothing an onClick handler would add over a
          direct top-level navigation. */}
      <a
        href={`${API_BASE_URL}/auth/google/authorize`}
        className="flex items-center justify-center gap-2 rounded-md border border-black/10 dark:border-white/15 py-2 text-sm font-medium text-black/80 hover:bg-black/5 dark:text-white/80 dark:hover:bg-white/5 w-full max-w-sm"
      >
        <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
          <path
            fill="#4285F4"
            d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z"
          />
          <path
            fill="#34A853"
            d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z"
          />
          <path
            fill="#FBBC05"
            d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34A21.93 21.93 0 0 0 2 24c0 3.55.85 6.91 2.34 9.88l7.35-5.7z"
          />
          <path
            fill="#EA4335"
            d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z"
          />
        </svg>
        Continue with Google
      </a>
    </>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";

import {
  disconnectLinkedInOAuth,
  getLinkedInOAuthAuthorizeUrl,
  getLinkedInOAuthStatus,
} from "@/lib/api/linkedinOauth";

// lucide-react doesn't ship brand icons in this version (see frontend/AGENTS.md) - inline SVG,
// same approach GoogleSignInButton.tsx already uses for the Google "G" mark.
function LinkedInIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.02-3.03-1.85-3.03-1.85 0-2.14 1.45-2.14 2.94v5.66H9.36V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.36-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45z" />
    </svg>
  );
}

export function LinkedInConnectSection() {
  const queryClient = useQueryClient();

  const { data: status, isLoading } = useQuery({
    queryKey: ["oauth", "linkedin", "status"],
    queryFn: getLinkedInOAuthStatus,
  });

  const { mutate: connect, isPending: isConnecting } = useMutation({
    mutationFn: getLinkedInOAuthAuthorizeUrl,
    // Full-page navigation, same reasoning as GoogleConnectSection - LinkedIn's consent screen
    // has to be the real top-level page, not something happening inside a background request.
    onSuccess: ({ authorize_url }) => {
      window.location.href = authorize_url;
    },
  });

  const { mutate: disconnect, isPending: isDisconnecting } = useMutation({
    mutationFn: disconnectLinkedInOAuth,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["oauth", "linkedin", "status"] }),
  });

  if (isLoading) return null;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-black/10 dark:border-white/15 p-3">
      <span className="flex items-center gap-1.5 text-xs font-medium text-black/60 dark:text-white/60">
        <LinkedInIcon />
        LinkedIn
      </span>
      {status?.connected ? (
        <>
          <p className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-500">
            <CheckCircle2 size={13} />
            Connected as {status.linkedin_name ?? status.linkedin_email}
          </p>
          <button
            onClick={() => disconnect()}
            disabled={isDisconnecting}
            className="self-start rounded-lg border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-red-500 hover:bg-red-500/5 disabled:opacity-50"
          >
            Disconnect
          </button>
        </>
      ) : (
        <>
          <p className="text-xs text-black/40 dark:text-white/40">
            Connect your LinkedIn account so the assistant knows who you are professionally.
            Limited to your basic profile - LinkedIn doesn&apos;t offer connections/feed access
            outside their partner program.
          </p>
          <button
            onClick={() => connect()}
            disabled={isConnecting}
            className="self-start rounded-lg bg-black dark:bg-white px-3 py-1.5 text-xs text-white dark:text-black disabled:opacity-50"
          >
            {isConnecting ? "Redirecting..." : "Connect LinkedIn account"}
          </button>
        </>
      )}
    </div>
  );
}

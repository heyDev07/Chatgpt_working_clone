"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Mail } from "lucide-react";
import { useState } from "react";

import {
  disconnectGoogleOAuth,
  getGoogleOAuthAuthorizeUrl,
  getGoogleOAuthStatus,
  testGoogleOAuthConnection,
} from "@/lib/api/oauth";
import { ApiError } from "@/lib/api/client";

export function GoogleConnectSection() {
  const queryClient = useQueryClient();
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const { data: status, isLoading } = useQuery({
    queryKey: ["oauth", "google", "status"],
    queryFn: getGoogleOAuthStatus,
  });

  const { mutate: connect, isPending: isConnecting } = useMutation({
    mutationFn: getGoogleOAuthAuthorizeUrl,
    // Full-page navigation, not a fetch redirect - Google's consent screen has to be the real
    // top-level page the user interacts with and approves, not something happening inside a
    // background request.
    onSuccess: ({ authorize_url }) => {
      window.location.href = authorize_url;
    },
  });

  const { mutate: disconnect, isPending: isDisconnecting } = useMutation({
    mutationFn: disconnectGoogleOAuth,
    onSuccess: () => {
      setTestResult(null);
      setTestError(null);
      queryClient.invalidateQueries({ queryKey: ["oauth", "google", "status"] });
    },
  });

  const { mutate: runTest, isPending: isTesting } = useMutation({
    mutationFn: testGoogleOAuthConnection,
    onSuccess: (data) => {
      setTestError(null);
      setTestResult(`Connected to ${data.email_address} - ${data.total_messages} messages in Gmail`);
    },
    onError: (err) => {
      setTestResult(null);
      setTestError(err instanceof ApiError ? err.message : "Connection test failed");
    },
  });

  if (isLoading) return null;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-black/10 dark:border-white/15 p-3">
      <span className="flex items-center gap-1.5 text-xs font-medium text-black/60 dark:text-white/60">
        <Mail size={13} />
        Google (Gmail + Calendar)
      </span>
      {status?.connected ? (
        <>
          <p className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-500">
            <CheckCircle2 size={13} />
            Connected as {status.google_email}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => runTest()}
              disabled={isTesting}
              className="flex-1 rounded-lg border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10 disabled:opacity-50"
            >
              {isTesting ? "Testing..." : "Test connection"}
            </button>
            <button
              onClick={() => disconnect()}
              disabled={isDisconnecting}
              className="flex-1 rounded-lg border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-red-500 hover:bg-red-500/5 disabled:opacity-50"
            >
              Disconnect
            </button>
          </div>
          {testResult && <p className="text-xs text-black/50 dark:text-white/50">{testResult}</p>}
          {testError && <p className="text-xs text-red-500">{testError}</p>}
        </>
      ) : (
        <>
          <p className="text-xs text-black/40 dark:text-white/40">
            Connect your Google account to let the assistant read your Gmail and Calendar.
          </p>
          <button
            onClick={() => connect()}
            disabled={isConnecting}
            className="self-start rounded-lg bg-black dark:bg-white px-3 py-1.5 text-xs text-white dark:text-black disabled:opacity-50"
          >
            {isConnecting ? "Redirecting..." : "Connect Google account"}
          </button>
        </>
      )}
    </div>
  );
}

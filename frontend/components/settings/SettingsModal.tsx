"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Monitor, Moon, Sun, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { deleteAccount } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthContext";
import { useTheme, type Theme } from "@/lib/theme/ThemeContext";

const THEME_OPTIONS: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function DeleteAccountSection() {
  const { logout } = useAuth();
  const router = useRouter();
  const [isConfirming, setIsConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { mutate: remove, isPending } = useMutation({
    mutationFn: () => deleteAccount(password),
    onSuccess: async () => {
      await logout();
      router.push("/login");
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Failed to delete account");
    },
  });

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-red-500/30 p-3">
      <span className="flex items-center gap-1.5 text-xs font-medium text-red-500">
        <AlertTriangle size={13} />
        Delete account
      </span>
      <p className="text-xs text-black/40 dark:text-white/40">
        Permanently deletes your account and everything in it - conversations, memories, documents,
        folders, and tags. This cannot be undone.
      </p>
      {!isConfirming ? (
        <button
          onClick={() => setIsConfirming(true)}
          className="self-start text-xs text-red-500 hover:underline"
        >
          Delete my account
        </button>
      ) : (
        <div className="flex flex-col gap-2">
          <input
            type="password"
            autoFocus
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setError(null);
            }}
            placeholder="Confirm your password"
            className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-1.5 text-xs outline-none placeholder:text-black/30 dark:placeholder:text-white/30"
          />
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={() => {
                setIsConfirming(false);
                setPassword("");
                setError(null);
              }}
              className="flex-1 rounded-lg border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10"
            >
              Cancel
            </button>
            <button
              onClick={() => remove()}
              disabled={isPending || !password}
              className="flex-1 rounded-lg bg-red-500 px-3 py-1.5 text-xs text-white hover:bg-red-600 disabled:opacity-50"
            >
              {isPending ? "Deleting..." : "Permanently delete"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const { theme, setTheme } = useTheme();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl bg-white dark:bg-neutral-900 border border-black/10 dark:border-white/10 shadow-xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-black/10 dark:border-white/10">
          <h2 className="text-sm font-semibold">Settings</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col gap-4 px-5 py-4">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium text-black/60 dark:text-white/60">Theme</span>
            <div className="grid grid-cols-3 gap-2">
              {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  onClick={() => setTheme(value)}
                  className={`flex flex-col items-center gap-1.5 rounded-lg border px-3 py-2.5 text-xs ${
                    theme === value
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400"
                      : "border-black/10 dark:border-white/15 text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/10"
                  }`}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <DeleteAccountSection />
        </div>
      </div>
    </div>
  );
}

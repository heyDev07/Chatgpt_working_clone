"use client";

import { BrainCog, FolderOpen, LogOut, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { DocumentManager } from "@/components/documents/DocumentManager";
import { MemoryManager } from "@/components/memory/MemoryManager";
import { ConversationList } from "@/components/sidebar/ConversationList";
import { NewChatButton } from "@/components/sidebar/NewChatButton";
import { useAuth } from "@/lib/auth/AuthContext";

export default function ChatLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [showMemories, setShowMemories] = useState(false);
  const [showDocuments, setShowDocuments] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading || !user) {
    return (
      <main className="flex-1 flex items-center justify-center bg-white dark:bg-[#212121]">
        <p className="text-sm text-black/40 dark:text-white/40">Loading...</p>
      </main>
    );
  }

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const initials = (user.full_name || user.email).slice(0, 1).toUpperCase();

  return (
    <div className="relative flex flex-1 overflow-hidden bg-white dark:bg-[#212121]">
      <aside
        className={`flex-shrink-0 bg-neutral-50 dark:bg-[#171717] flex flex-col overflow-hidden transition-[width] duration-200 ease-in-out ${
          isSidebarOpen ? "w-64" : "w-0"
        }`}
      >
        {/* Fixed-width inner wrapper: the outer <aside> animates width and clips via
            overflow-hidden, so content is clipped during the slide rather than reflowing. */}
        <div className="flex h-full w-64 flex-col p-2 gap-2">
          <div className="flex items-center gap-1">
            <div className="flex-1 min-w-0">
              <NewChatButton />
            </div>
            <button
              onClick={() => setIsSidebarOpen(false)}
              aria-label="Collapse sidebar"
              className="flex-shrink-0 rounded-lg p-2 text-black/50 hover:bg-black/5 dark:text-white/50 dark:hover:bg-white/10"
            >
              <PanelLeftClose size={18} />
            </button>
          </div>
          <div className="flex-1 overflow-hidden px-1">
            <ConversationList />
          </div>
          <button
            onClick={() => setShowDocuments(true)}
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-black/70 hover:bg-black/5 dark:text-white/70 dark:hover:bg-white/10"
          >
            <FolderOpen size={16} />
            Knowledge base
          </button>
          <button
            onClick={() => setShowMemories(true)}
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-black/70 hover:bg-black/5 dark:text-white/70 dark:hover:bg-white/10"
          >
            <BrainCog size={16} />
            Memories
          </button>
          <div className="border-t border-black/10 dark:border-white/10 pt-2 flex items-center gap-2 px-1 py-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/5">
            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-medium text-white">
              {initials}
            </div>
            <span className="flex-1 truncate text-sm text-black/80 dark:text-white/80">
              {user.full_name || user.email}
            </span>
            <button
              onClick={handleLogout}
              aria-label="Log out"
              className="flex-shrink-0 text-black/40 hover:text-black dark:text-white/40 dark:hover:text-white"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {!isSidebarOpen && (
        <button
          onClick={() => setIsSidebarOpen(true)}
          aria-label="Expand sidebar"
          className="absolute left-2 top-2 z-10 rounded-lg p-2 text-black/50 hover:bg-black/5 dark:text-white/50 dark:hover:bg-white/10"
        >
          <PanelLeftOpen size={18} />
        </button>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">{children}</div>

      {showMemories && <MemoryManager onClose={() => setShowMemories(false)} />}
      {showDocuments && <DocumentManager onClose={() => setShowDocuments(false)} />}
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";

type NavItem = {
  href: string;
  label: string;
  icon: ReactNode;
};

const NAV_ITEMS: NavItem[] = [
  {
    href: "/dashboard",
    label: "Documents",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-4.5 w-4.5">
        <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M14 3v5h5M9 13h6M9 17h6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/repositories",
    label: "Repositories",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-4.5 w-4.5">
        <path d="M3 5a2 2 0 012-2h4l2 2h8a2 2 0 012 2v11a2 2 0 01-2 2H5a2 2 0 01-2-2V5z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    href: "/query",
    label: "Ask",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-4.5 w-4.5">
        <path d="M21 12a9 9 0 01-12.8 8.2L3 21l.8-5.2A9 9 0 1121 12z" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M9.5 9a2.5 2.5 0 015 0c0 1.7-2.5 2-2.5 3.5M12 16.5h.01" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/evaluate",
    label: "Evaluate",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-4.5 w-4.5">
        <path d="M4 5h16M6 5v14a1 1 0 001 1h10a1 1 0 001-1V5" strokeLinecap="round" />
        <path d="M9 3h6v2H9zM9.5 10l2 2.5 2.5-4M9.5 15l2 2.5 2.5-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, token, status, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (status === "loading") return;
    if (status !== "authenticated" || !token) {
      router.replace("/login");
    }
  }, [status, token, router]);

  if (status === "loading" || status !== "authenticated") {
    return (
      <div className="flex min-h-full flex-1 items-center justify-center">
        <Spinner className="h-6 w-6 text-zinc-500" />
      </div>
    );
  }

  const displayName = user?.name || user?.email?.split("@")[0] || "User";

  const handleLogout = () => {
    logout();
    router.replace("/");
  };

  const navList = (
    <nav className="flex flex-col gap-1 px-3">
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setSidebarOpen(false)}
            className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              active
                ? "bg-indigo-500/15 text-indigo-300 ring-1 ring-inset ring-indigo-500/20"
                : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
            }`}
          >
            {item.icon}
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );

  const sidebarContent = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-sm font-bold text-white shadow-lg shadow-indigo-950/50">
          C
        </div>
        <div>
          <p className="text-sm font-semibold tracking-tight text-zinc-100">
            ContextHub
          </p>
          <p className="text-[11px] text-zinc-500">Knowledge & Code RAG</p>
        </div>
      </div>

      <div className="mt-2 flex-1 overflow-y-auto">{navList}</div>

      <div className="border-t border-white/5 p-4">
        <div className="mb-3 flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-zinc-700 to-zinc-800 text-xs font-semibold text-zinc-200 ring-1 ring-white/10">
            {displayName.slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-zinc-200">
              {displayName}
            </p>
            <p className="truncate text-[11px] text-zinc-500">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-400 transition-colors hover:bg-white/5 hover:text-zinc-100"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-4.5 w-4.5">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-full bg-zinc-950">
      <div className="flex min-h-screen">
        {/* Desktop sidebar */}
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-white/5 bg-zinc-950 lg:block">
          {sidebarContent}
        </aside>

        {/* Mobile sidebar */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setSidebarOpen(false)}
            />
            <aside className="absolute inset-y-0 left-0 w-64 border-r border-white/10 bg-zinc-950 shadow-2xl">
              {sidebarContent}
            </aside>
          </div>
        )}

        <div className="flex w-full flex-col lg:pl-64">
          {/* Top bar */}
          <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-white/5 bg-zinc-950/80 px-4 backdrop-blur lg:px-8">
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-white/5 hover:text-zinc-100 lg:hidden"
              aria-label="Open menu"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
              </svg>
            </button>

            <div className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 ring-1 ring-inset ring-emerald-500/20">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span className="text-[11px] font-medium text-emerald-400">
                API connected
              </span>
            </div>

            <div className="ml-auto flex items-center gap-2 text-xs text-zinc-500">
              <span className="hidden sm:inline">v5 · {user?.email}</span>
            </div>
          </header>

          <main className="flex-1 px-4 py-6 lg:px-8 lg:py-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
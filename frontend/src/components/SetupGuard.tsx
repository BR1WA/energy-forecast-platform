"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";
import { settingsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function SetupGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const setupCheckKey = isAuthenticated && user?.role !== 'admin'
    ? `${user?.id ?? 'authenticated'}:${pathname}`
    : null;
  const [checkedKey, setCheckedKey] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !setupCheckKey) return;
    let cancelled = false;

    const checkSetupStatus = async () => {
      try {
        const data = await settingsApi.getSetupStatus();
        if (!data.is_setup_complete && pathname !== "/setup" && pathname !== "/login" && pathname !== "/register") {
          router.push("/setup");
        } else if (data.is_setup_complete && pathname === "/setup") {
          router.push("/dashboard");
        }
      } catch (err) {
        console.error("Failed to check setup status", err);
      } finally {
        if (!cancelled) setCheckedKey(setupCheckKey);
      }
    };

    void checkSetupStatus();
    return () => {
      cancelled = true;
    };
  }, [authLoading, pathname, router, setupCheckKey]);

  const isChecking = authLoading || (setupCheckKey !== null && checkedKey !== setupCheckKey);

  if (isChecking || authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0F1C]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return <>{children}</>;
}

"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";
import { settingsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function SetupGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    if (!isAuthenticated) {
      setIsChecking(false);
      return;
    }

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
        setIsChecking(false);
      }
    };

    checkSetupStatus();
  }, [pathname, router, isAuthenticated, authLoading]);

  if (isChecking || authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0F1C]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return <>{children}</>;
}

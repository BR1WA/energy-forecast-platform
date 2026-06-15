"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";

export function SetupGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const checkSetupStatus = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/v1/settings/setup-status");
        if (res.ok) {
          const data = await res.json();
          if (!data.is_setup_complete && pathname !== "/setup" && pathname !== "/login" && pathname !== "/register") {
            router.push("/setup");
          } else if (data.is_setup_complete && pathname === "/setup") {
            router.push("/dashboard");
          }
        }
      } catch (err) {
        console.error("Failed to check setup status", err);
      } finally {
        setIsChecking(false);
      }
    };

    checkSetupStatus();
  }, [pathname, router]);

  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0F1C]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return <>{children}</>;
}

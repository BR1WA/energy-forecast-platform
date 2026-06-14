import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { I18nProvider } from "@/lib/i18n";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "EnergyAI — Smart Energy Management",
  description:
    "Premium energy consumption forecasting platform powered by AI",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col bg-[#0A0F1C] text-slate-200" suppressHydrationWarning>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          <I18nProvider>
            <AuthProvider>
              {children}
              <Toaster
                position="top-right"
                toastOptions={{
                  style: {
                    background: "#111827",
                    border: "1px solid rgba(59, 130, 246, 0.1)",
                    color: "#E2E8F0",
                  },
                }}
              />
            </AuthProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
